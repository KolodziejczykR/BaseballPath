"""
Stripe billing integration router — per-evaluation payments only.

There is a single checkout flow (`/billing/create-eval-checkout`) and the
webhook only cares about `checkout.session.completed` for `eval_purchase`.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.pricing_service import get_eval_price

logger = logging.getLogger(__name__)

try:
    import stripe
except Exception:  # pragma: no cover - stripe may be unavailable in some envs
    stripe = None

router = APIRouter()


def _require_stripe() -> Any:
    if stripe is None:
        raise HTTPException(
            status_code=503,
            detail="Stripe SDK is not installed. Add `stripe` to backend dependencies.",
        )

    stripe_key = os.getenv("STRIPE_SECRET_KEY")
    if not stripe_key:
        raise HTTPException(
            status_code=503,
            detail="Stripe is not configured. Set STRIPE_SECRET_KEY.",
        )
    stripe.api_key = stripe_key
    return stripe


class CreateEvalCheckoutRequest(BaseModel):
    session_token: str = Field(..., description="Session token from /evaluations/preview")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/create-eval-checkout")
async def create_eval_checkout(
    payload: CreateEvalCheckoutRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create a Stripe Checkout Session for a one-time evaluation payment. Auth required."""
    stripe_client = _require_stripe()

    pricing = get_eval_price(current_user.user_id)
    price_cents = pricing["price_cents"]
    is_first = pricing["is_first_eval"]

    supabase = require_supabase_admin_client()
    purchase_result = (
        supabase.table("eval_purchases")
        .insert(
            {
                "user_id": current_user.user_id,
                "amount_cents": price_cents,
                "currency": "usd",
                "status": "pending",
                "is_first_eval": is_first,
            }
        )
        .execute()
    )
    if not purchase_result.data:
        raise HTTPException(status_code=500, detail="Failed to create purchase record")
    purchase_id = purchase_result.data[0]["id"]

    origin = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    success_url = (
        payload.success_url
        or f"{origin}/predict/results?purchase_id={purchase_id}&session_token={payload.session_token}"
    )
    cancel_url = payload.cancel_url or f"{origin}/predict?checkout=cancelled"

    label = "BaseballPath Evaluation (First)" if is_first else "BaseballPath Evaluation"

    session = stripe_client.checkout.Session.create(
        mode="payment",
        line_items=[
            {
                "price_data": {
                    "currency": "usd",
                    "unit_amount": price_cents,
                    "product_data": {"name": label},
                },
                "quantity": 1,
            }
        ],
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=current_user.email,
        client_reference_id=current_user.user_id,
        metadata={
            "purchase_id": purchase_id,
            "session_token": payload.session_token,
            "payment_type": "eval_purchase",
            "user_id": current_user.user_id,
        },
    )

    supabase.table("eval_purchases").update(
        {
            "stripe_checkout_session_id": session.id,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", purchase_id).execute()

    return {
        "checkout_url": session.url,
        "session_id": session.id,
        "purchase_id": purchase_id,
    }


@router.post("/webhook")
async def billing_webhook(request: Request) -> Dict[str, Any]:
    stripe_client = _require_stripe()
    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Set STRIPE_WEBHOOK_SECRET for billing webhooks")

    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    if not signature:
        raise HTTPException(status_code=400, detail="Missing Stripe signature")

    try:
        event = stripe_client.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(exc)}") from exc

    event_type = event.get("type")
    event_data = ((event.get("data") or {}).get("object")) or {}

    if event_type == "checkout.session.completed":
        metadata = event_data.get("metadata") or {}
        if metadata.get("payment_type") != "eval_purchase":
            return {"received": True, "ignored": True}

        purchase_id = metadata.get("purchase_id")
        if not purchase_id:
            logger.warning("checkout.session.completed missing purchase_id in metadata")
            return {"received": True}

        supabase = require_supabase_admin_client()
        payment_intent_id = event_data.get("payment_intent")
        supabase.table("eval_purchases").update(
            {
                "status": "completed",
                "stripe_payment_intent_id": str(payment_intent_id) if payment_intent_id else None,
                "stripe_checkout_session_id": event_data.get("id"),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", purchase_id).execute()
        logger.info("Eval purchase %s marked completed", purchase_id)

    return {"received": True}
