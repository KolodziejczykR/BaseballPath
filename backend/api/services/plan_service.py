"""
Plan and usage helpers for entitlements and billing state.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException, status

from ..clients.supabase import require_supabase_admin_client

PLAN_STARTER = "starter"
PLAN_PRO = "pro"
PLAN_ELITE = "elite"
VALID_PLAN_TIERS = {PLAN_STARTER, PLAN_PRO, PLAN_ELITE}

ACTIVE_STATUSES = {"active", "trialing", "past_due"}

PLAN_EVAL_LIMITS = {
    PLAN_STARTER: 5,
    PLAN_PRO: 50,
    PLAN_ELITE: None,
}

PLAN_LLM_ENABLED = {
    PLAN_STARTER: False,
    PLAN_PRO: False,
    PLAN_ELITE: True,
}


@dataclass
class EffectivePlan:
    plan_tier: str
    status: str
    subscription: Optional[Dict[str, Any]]
    monthly_eval_limit: Optional[int]
    llm_enabled: bool


@dataclass
class UsageSnapshot:
    period_start: date
    eval_count: int
    llm_count: int


def get_current_period_start() -> date:
    now = datetime.now(timezone.utc)
    return date(year=now.year, month=now.month, day=1)


def _row_to_dict(row: Any) -> Dict[str, Any]:
    if isinstance(row, dict):
        return row
    return dict(row)  # pragma: no cover - defensive fallback


def ensure_profile_exists(user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    existing = (
        supabase.table("profiles")
        .select("*")
        .eq("id", user_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        return _row_to_dict(existing.data[0])

    insert_payload: Dict[str, Any] = {"id": user_id}
    if email:
        local_part = email.split("@")[0]
        insert_payload["full_name"] = local_part

    inserted = (
        supabase.table("profiles")
        .insert(insert_payload)
        .execute()
    )
    if not inserted.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create profile row",
        )
    return _row_to_dict(inserted.data[0])


def get_profile(user_id: str, email: Optional[str] = None) -> Dict[str, Any]:
    return ensure_profile_exists(user_id=user_id, email=email)


def update_profile(user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
    supabase = require_supabase_admin_client()
    response = (
        supabase.table("profiles")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Profile update failed",
        )
    return _row_to_dict(response.data[0])


def get_subscription_row(user_id: str) -> Optional[Dict[str, Any]]:
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
    return _row_to_dict(response.data[0])


def get_effective_plan(user_id: str) -> EffectivePlan:
    subscription = get_subscription_row(user_id)
    if subscription is None:
        plan_tier = PLAN_STARTER
        status_value = "none"
    else:
        raw_plan = (subscription.get("plan_tier") or PLAN_STARTER).lower()
        plan_tier = raw_plan if raw_plan in VALID_PLAN_TIERS else PLAN_STARTER
        status_value = (subscription.get("status") or "unknown").lower()
        if status_value not in ACTIVE_STATUSES:
            plan_tier = PLAN_STARTER

    return EffectivePlan(
        plan_tier=plan_tier,
        status=status_value,
        subscription=subscription,
        monthly_eval_limit=PLAN_EVAL_LIMITS[plan_tier],
        llm_enabled=PLAN_LLM_ENABLED[plan_tier],
    )


def get_monthly_usage(user_id: str, period_start: Optional[date] = None) -> UsageSnapshot:
    supabase = require_supabase_admin_client()
    resolved_period = period_start or get_current_period_start()
    response = (
        supabase.table("plan_usage_monthly")
        .select("*")
        .eq("user_id", user_id)
        .eq("period_start", resolved_period.isoformat())
        .limit(1)
        .execute()
    )
    if not response.data:
        return UsageSnapshot(
            period_start=resolved_period,
            eval_count=0,
            llm_count=0,
        )
    row = _row_to_dict(response.data[0])
    return UsageSnapshot(
        period_start=resolved_period,
        eval_count=int(row.get("eval_count") or 0),
        llm_count=int(row.get("llm_count") or 0),
    )


def _upsert_usage(user_id: str, period_start: date, eval_count: int, llm_count: int) -> UsageSnapshot:
    supabase = require_supabase_admin_client()
    upsert_payload = {
        "user_id": user_id,
        "period_start": period_start.isoformat(),
        "eval_count": eval_count,
        "llm_count": llm_count,
    }
    response = (
        supabase.table("plan_usage_monthly")
        .upsert(upsert_payload, on_conflict="user_id,period_start")
        .execute()
    )
    if not response.data:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to write monthly usage counters",
        )
    row = _row_to_dict(response.data[0])
    return UsageSnapshot(
        period_start=period_start,
        eval_count=int(row.get("eval_count") or 0),
        llm_count=int(row.get("llm_count") or 0),
    )


def increment_usage(
    user_id: str,
    *,
    evaluation_increment: int = 0,
    llm_increment: int = 0,
    period_start: Optional[date] = None,
) -> UsageSnapshot:
    resolved_period = period_start or get_current_period_start()
    snapshot = get_monthly_usage(user_id, resolved_period)
    return _upsert_usage(
        user_id=user_id,
        period_start=resolved_period,
        eval_count=snapshot.eval_count + max(evaluation_increment, 0),
        llm_count=snapshot.llm_count + max(llm_increment, 0),
    )


def remaining_evaluations(effective_plan: EffectivePlan, usage: UsageSnapshot) -> Optional[int]:
    if effective_plan.monthly_eval_limit is None:
        return None
    remaining = effective_plan.monthly_eval_limit - usage.eval_count
    return max(remaining, 0)


def enforce_evaluation_quota(user_id: str, effective_plan: EffectivePlan) -> UsageSnapshot:
    usage = get_monthly_usage(user_id)
    limit = effective_plan.monthly_eval_limit
    if limit is not None and usage.eval_count >= limit:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "error": "evaluation_quota_exceeded",
                "plan_tier": effective_plan.plan_tier,
                "monthly_limit": limit,
                "current_usage": usage.eval_count,
                "remaining_evals": 0,
                "period_start": usage.period_start.isoformat(),
            },
        )
    return usage
