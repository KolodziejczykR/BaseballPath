"""Health check endpoints.

Three levels:
  * GET /ping       — process-level liveness. No external deps. Used by
                      Render's default health check; must always return 200
                      even if Supabase is down.
  * GET /health     — readiness. Checks that critical env vars are set and
                      Supabase is reachable. Returns 503 if any check fails.
  * GET /health/deep — full dependency probe (Supabase + OpenAI key + Stripe
                       key + Celery broker). Slower; intended for ops dashboards
                       and post-deploy smoke tests, not for hot health checks.

Render's load balancer does NOT take traffic away from a node based on a
503 from /health — but a monitoring service (UptimeRobot, etc.) can page
on it, which is the whole point.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ..clients.supabase import get_supabase_admin_client


router = APIRouter()
logger = logging.getLogger(__name__)


# Required env vars for the full app to function. Missing any of these is
# a configuration error worthy of a 503 from /health.
_REQUIRED_ENV = (
    "SUPABASE_URL",
    "SUPABASE_SERVICE_KEY",
    "SUPABASE_ANON_KEY",
    "OPENAI_API_KEY",
    "STRIPE_SECRET_KEY",
    "STRIPE_WEBHOOK_SECRET",
)


@router.get("/ping")
def ping() -> Dict[str, str]:
    """Liveness — process is up. Always 200, never touches dependencies.

    Used as Render's default health endpoint so a transient Supabase
    outage doesn't take the whole service offline."""
    return {"status": "ok"}


@router.get("/health")
def health() -> JSONResponse:
    """Readiness — required env vars set + Supabase reachable.

    Returns 200 with status="ok" if all checks pass, 503 with the failed
    checks listed otherwise."""
    checks: Dict[str, Any] = {}
    failed: List[str] = []

    # Env-var presence
    for name in _REQUIRED_ENV:
        present = bool(os.getenv(name))
        checks[f"env.{name}"] = "ok" if present else "missing"
        if not present:
            failed.append(f"env.{name}")

    # Supabase ping — cheapest possible read so we don't hammer the DB.
    try:
        sb = get_supabase_admin_client()
        if sb is None:
            checks["supabase"] = "client_unavailable"
            failed.append("supabase")
        else:
            # Pick a tiny, always-existing table. Limit 1, no count.
            sb.table("waitlist").select("id").limit(1).execute()
            checks["supabase"] = "ok"
    except Exception as exc:  # noqa: BLE001 — health endpoint must not raise
        logger.warning("Supabase health check failed: %s", exc)
        checks["supabase"] = f"error: {type(exc).__name__}"
        failed.append("supabase")

    if failed:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "failed": failed, "checks": checks},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "checks": checks},
    )


@router.get("/health/deep")
def health_deep() -> JSONResponse:
    """Full dependency probe — slower, includes Celery broker + secrets.

    Intended for ops dashboards / post-deploy smoke tests, not for the
    monitor's hot path."""
    checks: Dict[str, Any] = {}
    failed: List[str] = []

    # Run the standard readiness checks first.
    base_response = health()
    base_body = base_response.body
    import json as _json
    base = _json.loads(base_body) if base_body else {}
    checks.update(base.get("checks") or {})
    for f in base.get("failed") or []:
        if f not in failed:
            failed.append(f)

    # Celery broker reachability — only attempt if env var is set;
    # otherwise the missing-env check above already flagged it.
    broker_url = os.getenv("CELERY_BROKER_URL") or os.getenv("REDIS_URL")
    if broker_url:
        try:
            # Lazy import — Celery + Redis aren't on the hot path.
            import redis  # type: ignore
            r = redis.Redis.from_url(broker_url, socket_connect_timeout=2)
            r.ping()
            checks["celery_broker"] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("Celery broker health check failed: %s", exc)
            checks["celery_broker"] = f"error: {type(exc).__name__}"
            failed.append("celery_broker")
    else:
        checks["celery_broker"] = "not_configured"
        # Not failing here — broker only matters for deep research, and a
        # deploy without Celery is a known degraded mode.

    if failed:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "failed": failed, "checks": checks},
        )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok", "checks": checks},
    )
