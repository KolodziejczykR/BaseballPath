"""
Stripe billing integration router — per-evaluation payments only.

There is a single checkout flow (`/billing/create-eval-checkout`) and the
webhook only cares about `checkout.session.completed` for `eval_purchase`.
"""

from __future__ import annotations

import json
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
    # ------------------------------------------------------------------
    # FREE BETA: Stripe checkout is bypassed during the beta rollout so
    # we can collect feedback without paywalling. The original Stripe
    # flow below is preserved (commented) — uncomment the Stripe block
    # and remove the FREE BETA short-circuit to restore paid checkout.
    # ------------------------------------------------------------------
    # stripe_client = _require_stripe()

    pricing = get_eval_price(current_user.user_id)
    # price_cents = pricing["price_cents"]
    is_first = pricing["is_first_eval"]

    # FREE BETA: charge $0 and mark the purchase completed immediately so
    # the existing /evaluations/finalize gate (which requires status =
    # "completed") still works without the Stripe webhook firing.
    price_cents = 0

    supabase = require_supabase_admin_client()
    purchase_result = (
        supabase.table("eval_purchases")
        .insert(
            {
                "user_id": current_user.user_id,
                "amount_cents": price_cents,
                "currency": "usd",
                "status": "completed",  # FREE BETA: was "pending" — Stripe webhook normally flips this
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
    # cancel_url = payload.cancel_url or f"{origin}/predict?checkout=cancelled"

    # label = "BaseballPath Evaluation (First)" if is_first else "BaseballPath Evaluation"

    # ------------------------------------------------------------------
    # FREE BETA: Stripe Checkout Session creation is disabled. Restore
    # the block below (and the cancel_url / label / stripe_client lines
    # above) when re-enabling paid checkout.
    # ------------------------------------------------------------------
    # session = stripe_client.checkout.Session.create(
    #     mode="payment",
    #     line_items=[
    #         {
    #             "price_data": {
    #                 "currency": "usd",
    #                 "unit_amount": price_cents,
    #                 "product_data": {"name": label},
    #             },
    #             "quantity": 1,
    #         }
    #     ],
    #     success_url=success_url,
    #     cancel_url=cancel_url,
    #     customer_email=current_user.email,
    #     client_reference_id=current_user.user_id,
    #     metadata={
    #         "purchase_id": purchase_id,
    #         "session_token": payload.session_token,
    #         "payment_type": "eval_purchase",
    #         "user_id": current_user.user_id,
    #     },
    # )
    #
    # supabase.table("eval_purchases").update(
    #     {
    #         "stripe_checkout_session_id": session.id,
    #         "updated_at": datetime.now(timezone.utc).isoformat(),
    #     }
    # ).eq("id", purchase_id).execute()
    #
    # return {
    #     "checkout_url": session.url,
    #     "session_id": session.id,
    #     "purchase_id": purchase_id,
    # }

    # FREE BETA: skip Stripe entirely — point the frontend straight at
    # the success URL so its existing `window.location.href = checkout_url`
    # redirect lands on /predict/results, where finalize() will succeed
    # because the purchase is already marked completed above.
    return {
        "checkout_url": success_url,
        "session_id": None,
        "purchase_id": purchase_id,
    }


def _claim_stripe_event(supabase: Any, event_id: str, event_type: str) -> bool:
    """Try to claim a Stripe event for processing.

    Inserts ``(event_id, event_type)`` into ``stripe_events``. Returns True
    if this is the first time we've seen the event (i.e. we should process
    it), False if it's a duplicate Stripe retry.

    Stripe routinely re-delivers events on transient 2xx flakiness, network
    issues, or when our ack times out. Without this guard the same event
    can fire ``eval_purchases`` updates and downstream side effects
    multiple times. The unique constraint on ``stripe_events.event_id`` is
    what makes this safe under concurrency — two parallel webhook calls
    for the same event will both INSERT, but only one will succeed.
    """
    try:
        result = (
            supabase.table("stripe_events")
            .insert(
                {"event_id": event_id, "event_type": event_type},
                returning="minimal",
            )
            .execute()
        )
        # If insert returned data, we just claimed the event for the first time.
        return True
    except Exception as exc:
        # Most common cause: unique-constraint violation on event_id, which
        # means a sibling worker already claimed this event. Treat anything
        # that the DB rejects as "already processed" rather than re-running
        # the side effects. We log so a real DB outage is visible.
        message = str(exc).lower()
        if "duplicate" in message or "unique" in message or "23505" in message:
            return False
        logger.warning(
            "stripe_events claim failed for event_id=%s type=%s err=%s",
            event_id, event_type, exc,
        )
        return False


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
        # construct_event verifies the signature and parses the body. The
        # returned object is a stripe.Event (a StripeObject), which in some
        # SDK versions does NOT support .get() the way a plain dict does
        # — accessing event.get triggers __getattr__("get") and crashes
        # with AttributeError. After signature verification, we re-parse
        # the same raw bytes as a plain Python dict so the rest of this
        # handler can use familiar .get() access without surprises.
        stripe_client.Webhook.construct_event(payload, signature, webhook_secret)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid webhook signature: {str(exc)}") from exc

    try:
        event: Dict[str, Any] = json.loads(payload.decode("utf-8"))
    except Exception as exc:
        # If the payload validated but isn't parseable JSON, something is
        # very wrong — treat as a malformed request rather than a 500.
        raise HTTPException(status_code=400, detail="Webhook payload is not valid JSON") from exc

    event_id = event.get("id")
    event_type = event.get("type")
    event_data = ((event.get("data") or {}).get("object")) or {}

    if not event_id:
        logger.warning("Stripe webhook received with no event id; ignoring")
        return {"received": True, "ignored": True, "reason": "missing_event_id"}

    supabase = require_supabase_admin_client()

    # Idempotency layer 1: have we processed this exact event id already?
    if not _claim_stripe_event(supabase, event_id, event_type or ""):
        logger.info(
            "Stripe webhook duplicate event_id=%s type=%s — skipping",
            event_id, event_type,
        )
        return {"received": True, "duplicate": True}

    if event_type == "checkout.session.completed":
        metadata = event_data.get("metadata") or {}
        if metadata.get("payment_type") != "eval_purchase":
            return {"received": True, "ignored": True}

        purchase_id = metadata.get("purchase_id")
        if not purchase_id:
            logger.warning("checkout.session.completed missing purchase_id in metadata")
            return {"received": True}

        # Idempotency layer 2: only flip to completed if not already there.
        # Defense-in-depth in case the event-id dedupe is bypassed (manual
        # replay, restored backup, etc). Avoids re-stamping completed_at /
        # downstream consumers that watch for the transition.
        existing = (
            supabase.table("eval_purchases")
            .select("status")
            .eq("id", purchase_id)
            .limit(1)
            .execute()
        )
        if not existing.data:
            logger.warning(
                "checkout.session.completed for unknown purchase_id=%s",
                purchase_id,
            )
            return {"received": True}
        if existing.data[0].get("status") == "completed":
            logger.info(
                "checkout.session.completed for already-completed purchase_id=%s — skipping",
                purchase_id,
            )
            return {"received": True, "duplicate_completion": True}

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

    # ---------------------------------------------------------------------
    # Other event types — log explicitly so we have an audit trail and
    # don't pretend we handled them. None of these are "do nothing"
    # silently anymore. Add real handling for each as the billing flow
    # matures (refunds, dispute holds, etc.).
    # ---------------------------------------------------------------------

    # The Stripe metadata we need to correlate to a local purchase.
    metadata = event_data.get("metadata") or {}
    purchase_id_for_log = metadata.get("purchase_id")

    if event_type == "checkout.session.async_payment_failed":
        # User abandoned or the bank declined. Purchase remains 'pending';
        # the user can retry through a new checkout session. Logging here
        # so a spike in failures is visible in dashboards.
        logger.warning(
            "Stripe async payment failed: event_id=%s purchase_id=%s",
            event_id, purchase_id_for_log,
        )
        return {"received": True, "event_type": event_type, "logged": True}

    if event_type in ("payment_intent.payment_failed", "charge.failed"):
        logger.warning(
            "Stripe payment failed: event_id=%s type=%s purchase_id=%s",
            event_id, event_type, purchase_id_for_log,
        )
        return {"received": True, "event_type": event_type, "logged": True}

    if event_type in ("charge.refunded", "charge.refund.updated"):
        # Refunds aren't auto-handled yet — the user-facing story (revoke
        # access? credit a re-eval?) hasn't been decided. Log loudly so
        # we notice them while support is still manual.
        logger.warning(
            "Stripe refund event received but not auto-processed: "
            "event_id=%s type=%s purchase_id=%s — manual reconciliation needed",
            event_id, event_type, purchase_id_for_log,
        )
        return {"received": True, "event_type": event_type, "needs_manual_review": True}

    if event_type in (
        "charge.dispute.created",
        "charge.dispute.funds_withdrawn",
        "charge.dispute.closed",
    ):
        # Disputes are a strong "look at this now" signal.
        logger.error(
            "Stripe dispute event: event_id=%s type=%s purchase_id=%s — manual review required",
            event_id, event_type, purchase_id_for_log,
        )
        return {"received": True, "event_type": event_type, "needs_manual_review": True}

    # Any other event type (Stripe sends a lot we don't subscribe to). Log
    # at INFO so we have a record but don't alert.
    logger.info(
        "Stripe webhook unhandled event_type=%s event_id=%s",
        event_type, event_id,
    )
    return {"received": True, "event_type": event_type, "ignored": True}
