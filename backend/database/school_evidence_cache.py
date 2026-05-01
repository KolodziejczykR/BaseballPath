"""Read-side helper for the ``school_evidence_cache`` table.

Cache contains position-agnostic parsed roster + stats per school,
populated weekly by ``backend/scripts/refresh_school_evidence_cache.py``.
The deep-school-research worker reads from here in lieu of live fetching.

Anything older than ``TTL_DAYS`` or marked ``source_status='failed'`` is
treated as a miss; the worker then falls through to its existing
live-fetch path. This module is intentionally read-only — the cron
script handles writes.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from backend.api.clients.supabase import get_supabase_admin_client
from backend.llm.deep_school_insights.types import (
    MatchedPlayer,
    ParsedPlayer,
    ParsedStatLine,
)

logger = logging.getLogger(__name__)

# 2× the cron interval (weekly). Tolerates one missed cron run before
# the worker starts paying live-fetch costs again.
TTL_DAYS = 14

TABLE = "school_evidence_cache"


def _parse_dt(value: Any) -> Optional[datetime]:
    """Tolerant ISO-8601 parser for the timestamp Supabase returns."""
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_cache_batch(school_names: List[str]) -> Dict[str, Dict[str, Any]]:
    """Fetch fresh, non-failed cache rows for the given schools in one round-trip.

    Returns a dict keyed by school_name. Schools that miss, are stale
    (older than TTL_DAYS), or are marked source_status='failed' are
    omitted — the caller should treat omission as "no cache" and
    fall through to live fetch.
    """
    if not school_names:
        return {}

    client = get_supabase_admin_client()
    if client is None:
        # No Supabase configured (test envs, missing creds). Silent miss
        # is the right behavior here — worker keeps using live fetch.
        return {}

    try:
        resp = (
            client.table(TABLE)
            .select(
                "school_name, roster_url, matched_players, stats_available, "
                "source_status, fetched_at"
            )
            .in_("school_name", school_names)
            .execute()
        )
    except Exception as exc:
        logger.warning("school_evidence_cache lookup failed: %s", exc)
        return {}

    cutoff = datetime.now(timezone.utc) - timedelta(days=TTL_DAYS)
    fresh: Dict[str, Dict[str, Any]] = {}
    for row in resp.data or []:
        if row.get("source_status") == "failed":
            continue
        fetched_at = _parse_dt(row.get("fetched_at"))
        if fetched_at is None or fetched_at < cutoff:
            continue
        fresh[row["school_name"]] = row

    return fresh


def deserialize_matched_players(blob: Any) -> List[MatchedPlayer]:
    """Rehydrate JSON list (as stored in matched_players JSONB) into dataclasses.

    The cron writes ``[asdict(MatchedPlayer), ...]``; this is the inverse.
    Extra/missing fields are tolerated so a schema drift in either
    direction degrades gracefully (extra fields ignored; missing fields
    fall back to dataclass defaults).
    """
    if not blob:
        return []

    out: List[MatchedPlayer] = []
    for entry in blob:
        if not isinstance(entry, dict):
            continue
        player_d = entry.get("player") or {}
        out.append(
            MatchedPlayer(
                player=_dict_to_dataclass(player_d, ParsedPlayer),
                batting_stats=_dict_to_dataclass_or_none(
                    entry.get("batting_stats"), ParsedStatLine
                ),
                pitching_stats=_dict_to_dataclass_or_none(
                    entry.get("pitching_stats"), ParsedStatLine
                ),
            )
        )
    return out


def serialize_matched_players(matched: List[MatchedPlayer]) -> List[Dict[str, Any]]:
    """Inverse of deserialize_matched_players. Used by the cron writer."""
    return [asdict(m) for m in matched]


def _dict_to_dataclass(data: Dict[str, Any], cls):
    """Build a dataclass from a dict, ignoring unknown keys.

    Tolerates schema drift: a field added to the dataclass after the
    cache row was written gets the dataclass default; a field removed
    from the dataclass is silently dropped.
    """
    fields = {f for f in cls.__dataclass_fields__}
    return cls(**{k: v for k, v in data.items() if k in fields})


def _dict_to_dataclass_or_none(data: Optional[Dict[str, Any]], cls):
    if not data:
        return None
    return _dict_to_dataclass(data, cls)
