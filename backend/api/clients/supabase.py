"""
Shared Supabase admin client utilities for API routers.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import load_dotenv
from fastapi import HTTPException
from supabase import Client, create_client

load_dotenv()

_supabase_admin_client: Optional[Client] = None
_supabase_admin_initialized = False


def get_supabase_url() -> Optional[str]:
    return os.getenv("SUPABASE_URL")


def get_supabase_service_key() -> Optional[str]:
    return os.getenv("SUPABASE_SERVICE_KEY")


def get_supabase_anon_key() -> Optional[str]:
    return os.getenv("SUPABASE_ANON_KEY")


def get_supabase_admin_client() -> Optional[Client]:
    global _supabase_admin_client, _supabase_admin_initialized

    if _supabase_admin_initialized:
        return _supabase_admin_client

    _supabase_admin_initialized = True
    url = get_supabase_url()
    service_key = get_supabase_service_key()

    if not url or not service_key:
        _supabase_admin_client = None
        return None

    _supabase_admin_client = create_client(url, service_key)
    return _supabase_admin_client


def require_supabase_admin_client() -> Client:
    client = get_supabase_admin_client()
    if client is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "Supabase admin client is not configured. "
                "Set SUPABASE_URL and SUPABASE_SERVICE_KEY."
            ),
        )
    return client

