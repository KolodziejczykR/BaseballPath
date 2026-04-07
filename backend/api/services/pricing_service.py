"""
Per-evaluation pricing service.

Determines the price for a user's next evaluation based on their purchase history.
First evaluation: $69, subsequent evaluations: $29.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from ..clients.supabase import require_supabase_admin_client

logger = logging.getLogger(__name__)

FIRST_EVAL_PRICE_CENTS = 6900   # $69
REPEAT_EVAL_PRICE_CENTS = 2900  # $29


def get_eval_price(user_id: str) -> Dict[str, Any]:
    """Determine the price for the user's next evaluation."""
    supabase = require_supabase_admin_client()
    result = (
        supabase.table("eval_purchases")
        .select("id", count="exact")
        .eq("user_id", user_id)
        .eq("status", "completed")
        .execute()
    )
    count = result.count if result.count is not None else 0
    is_first = count == 0
    return {
        "price_cents": FIRST_EVAL_PRICE_CENTS if is_first else REPEAT_EVAL_PRICE_CENTS,
        "is_first_eval": is_first,
        "completed_eval_count": count,
    }
