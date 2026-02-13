"""
Stripe billing integration router.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from ..clients.supabase import require_supabase_admin_client
from ..deps.auth import AuthenticatedUser, get_current_user
from ..services.plan_service import (
    PLAN_ELITE,
    PLAN_PRO,
    PLAN_STARTER,
    VALID_PLAN_TIERS,
    get_profile,
)

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


def _stripe_price_ids() -> Dict[str, str]:
    plan_to_price = {
        PLAN_PRO: os.getenv("STRIPE_PRICE_ID_PRO", ""),
        PLAN_ELITE: os.getenv("STRIPE_PRICE_ID_ELITE", ""),
    }
    return {k: v for k, v in plan_to_price.items() if v}


def _to_iso(ts: Optional[int]) -> Optional[str]:
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def _get_subscription_by_user(user_id: str) -> Optional[Dict[str, Any]]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("subscriptions")
        .select("*")
        .eq("user_id", user_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return dict(response.data[0])


def _get_subscription_by_customer(customer_id: str) -> Optional[Dict[str, Any]]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("subscriptions")
        .select("*")
        .eq("stripe_customer_id", customer_id)
        .order("updated_at", desc=True)
        .limit(1)
        .execute()
    )
    if not response.data:
        return None
    return dict(response.data[0])


def _upsert_subscription(user_id: str, fields: Dict[str, Any]) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    existing = _get_subscription_by_user(user_id)
    if existing:
        response = (
            supabase.table("subscriptions")
            .update(fields)
            .eq("id", existing["id"])
            .execute()
        )
    else:
        payload = dict(fields)
        payload["user_id"] = user_id
        response = (
            supabase.table("subscriptions")
            .insert(payload)
            .execute()
        )
    if not response.data:
        raise HTTPException(status_code=500, detail="Failed to write subscription row")
    return dict(response.data[0])


def _plan_tier_from_subscription_obj(subscription: Dict[str, Any]) -> str:
    price_id_to_plan = {v: k for k, v in _stripe_price_ids().items()}
    items = (((subscription.get("items") or {}).get("data")) or [])
    for item in items:
        price = item.get("price") or {}
        price_id = price.get("id")
        if price_id in price_id_to_plan:
            return price_id_to_plan[price_id]
    return PLAN_STARTER


def _sync_from_subscription_object(subscription: Dict[str, Any], user_id: Optional[str] = None) -> Dict[str, Any]:
    customer_id = subscription.get("customer")
    sub_id = subscription.get("id")
    status_value = subscription.get("status", "unknown")
    plan_tier = _plan_tier_from_subscription_obj(subscription)

    resolved_user_id = user_id
    if not resolved_user_id and customer_id:
        existing = _get_subscription_by_customer(str(customer_id))
        if existing:
            resolved_user_id = existing.get("user_id")

    if not resolved_user_id:
        metadata = subscription.get("metadata") or {}
        resolved_user_id = metadata.get("user_id")

    if not resolved_user_id:
        raise HTTPException(status_code=400, detail="Unable to map Stripe subscription to user")

    return _upsert_subscription(
        str(resolved_user_id),
        {
            "plan_tier": plan_tier,
            "status": status_value,
            "stripe_customer_id": str(customer_id) if customer_id else None,
            "stripe_subscription_id": str(sub_id) if sub_id else None,
            "current_period_start": _to_iso(subscription.get("current_period_start")),
            "current_period_end": _to_iso(subscription.get("current_period_end")),
            "cancel_at_period_end": bool(subscription.get("cancel_at_period_end", False)),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        },
    )


class CreateCheckoutSessionRequest(BaseModel):
    plan_tier: str = Field(..., description="Target plan tier: pro or elite")
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None


@router.post("/create-checkout-session")
async def create_checkout_session(
    payload: CreateCheckoutSessionRequest,
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    stripe_client = _require_stripe()
    get_profile(current_user.user_id, current_user.email)

    requested_tier = payload.plan_tier.lower()
    if requested_tier not in VALID_PLAN_TIERS or requested_tier == PLAN_STARTER:
        raise HTTPException(status_code=400, detail="plan_tier must be `pro` or `elite`")

    price_ids = _stripe_price_ids()
    price_id = price_ids.get(requested_tier)
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail=f"Stripe price id is not configured for plan `{requested_tier}`",
        )

    current_sub = _get_subscription_by_user(current_user.user_id) or {}
    customer_id = current_sub.get("stripe_customer_id")
    if not customer_id:
        customer = stripe_client.Customer.create(
            email=current_user.email,
            metadata={"user_id": current_user.user_id},
        )
        customer_id = customer.get("id")
        _upsert_subscription(
            current_user.user_id,
            {
                "plan_tier": PLAN_STARTER,
                "status": "incomplete",
                "stripe_customer_id": customer_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )

    origin = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    success_url = payload.success_url or f"{origin}/plans?checkout=success"
    cancel_url = payload.cancel_url or f"{origin}/plans?checkout=cancelled"

    session = stripe_client.checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "user_id": current_user.user_id,
            "plan_tier": requested_tier,
        },
        client_reference_id=current_user.user_id,
    )
    return {"checkout_url": session.url, "session_id": session.id}


@router.post("/create-portal-session")
async def create_portal_session(
    current_user: AuthenticatedUser = Depends(get_current_user),
) -> Dict[str, Any]:
    stripe_client = _require_stripe()
    sub = _get_subscription_by_user(current_user.user_id)
    if not sub or not sub.get("stripe_customer_id"):
        raise HTTPException(status_code=404, detail="No Stripe customer is linked to this account")

    origin = os.getenv("APP_BASE_URL", "http://localhost:3000").rstrip("/")
    session = stripe_client.billing_portal.Session.create(
        customer=sub["stripe_customer_id"],
        return_url=f"{origin}/plans",
    )
    return {"portal_url": session.url}


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
        user_id = ((event_data.get("metadata") or {}).get("user_id")) or event_data.get("client_reference_id")
        subscription_id = event_data.get("subscription")
        customer_id = event_data.get("customer")
        if subscription_id:
            subscription = stripe_client.Subscription.retrieve(subscription_id)
            _sync_from_subscription_object(subscription, user_id=user_id)
        elif user_id:
            _upsert_subscription(
                str(user_id),
                {
                    "status": "active",
                    "stripe_customer_id": str(customer_id) if customer_id else None,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                },
            )
    elif event_type in {"customer.subscription.updated", "customer.subscription.deleted"}:
        _sync_from_subscription_object(event_data)

    return {"received": True}
