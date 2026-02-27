"""Shared Supabase Storage helpers."""

from __future__ import annotations

import os
from typing import Optional

from api.clients.supabase import require_supabase_admin_client

PHOTO_BUCKET = os.getenv("SUPABASE_PLAYER_PHOTO_BUCKET", "player-photos")


def signed_photo_url(storage_path: Optional[str]) -> Optional[str]:
    """Return a 24-hour signed URL for a player photo, or None."""
    if not storage_path:
        return None
    supabase = require_supabase_admin_client()
    try:
        signed = supabase.storage.from_(PHOTO_BUCKET).create_signed_url(storage_path, 3600 * 24)
    except Exception:
        return None

    if isinstance(signed, str):
        return signed
    if isinstance(signed, dict):
        return signed.get("signedURL") or signed.get("signed_url")
    if hasattr(signed, "signedURL"):
        return getattr(signed, "signedURL")
    return None
