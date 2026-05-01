"""Sentry initialization shared across web and worker processes.

The web process (api/main.py) and the Celery worker process (llm/tasks.py)
each need their own Sentry init because they run in separate Python
processes. This module is the single source of truth for the configuration
so the two stay in sync.

Behavior is gated on the SENTRY_DSN env var:
  - SENTRY_DSN unset: no-op (dev environments without observability).
  - SENTRY_DSN set: send unhandled exceptions and (optional) traces to Sentry.

Required env:
  - SENTRY_DSN — Sentry project DSN.

Optional env:
  - ENVIRONMENT — "production", "staging", "development". Default
    "development". Tags every event so prod alerts don't fire on dev runs.
  - RELEASE_VERSION (or RENDER_GIT_COMMIT) — git commit hash. Lets Sentry
    pin each error to the deploy that introduced it.
  - SENTRY_TRACES_SAMPLE_RATE — 0.0 to 1.0; fraction of requests to sample
    for performance traces. Default 0.0 (errors only). Bump to 0.05-0.1
    when you want APM data.
  - SENTRY_PROFILES_SAMPLE_RATE — fraction of sampled traces to profile.
    Default 0.0.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import sentry_sdk

logger = logging.getLogger(__name__)


_INITIALIZED = False


def init_sentry(*, with_celery: bool = False) -> bool:
    """Initialize Sentry for the current process.

    Idempotent — calling twice in the same process is a no-op. Returns
    True if Sentry was actually initialized (DSN present), False otherwise.

    Pass ``with_celery=True`` from the Celery worker entrypoint so task
    failures are also captured. The default (web) path picks up FastAPI
    and asyncio integrations automatically via Sentry's auto-detection.
    """
    global _INITIALIZED
    if _INITIALIZED:
        return True

    dsn = os.getenv("SENTRY_DSN")
    if not dsn:
        logger.info("SENTRY_DSN not set; Sentry disabled for this process")
        return False

    integrations = []
    if with_celery:
        # Lazy import — sentry_sdk's CeleryIntegration imports celery at
        # module load. We don't want the web process to drag celery in.
        from sentry_sdk.integrations.celery import CeleryIntegration
        integrations.append(CeleryIntegration())

    environment = os.getenv("ENVIRONMENT", "development")
    release = _resolve_release()

    sentry_sdk.init(
        dsn=dsn,
        environment=environment,
        release=release,
        # Errors-only by default. Bump SENTRY_TRACES_SAMPLE_RATE if you want
        # APM data (request-latency, transaction tracing). At 0.0 we send
        # zero performance events but still capture every exception.
        traces_sample_rate=_float_env("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        profiles_sample_rate=_float_env("SENTRY_PROFILES_SAMPLE_RATE", 0.0),
        # Stack frames + locals attached to every event, even non-exception
        # captures via capture_message().
        attach_stacktrace=True,
        # Default False already, but make it explicit. Stops Sentry from
        # auto-shipping cookies, IPs, request bodies, and user emails. We
        # opt-in to user/request context per-route via set_user / set_tag.
        send_default_pii=False,
        # Don't sample individual error events — we want every exception
        # in beta. (sample_rate is for ERRORS, traces_sample_rate is for
        # performance transactions; they are independent.)
        sample_rate=1.0,
        integrations=integrations,
        before_send=_redact_event,
    )
    _INITIALIZED = True
    logger.info(
        "Sentry initialized: env=%s release=%s traces_rate=%.2f celery=%s",
        environment,
        release or "(unset)",
        _float_env("SENTRY_TRACES_SAMPLE_RATE", 0.0),
        with_celery,
    )
    return True


def _resolve_release() -> Optional[str]:
    """Pick the best release identifier from the environment.

    Render exposes RENDER_GIT_COMMIT automatically. RELEASE_VERSION is the
    explicit override for local builds or non-Render deploys.
    """
    return (
        os.getenv("RELEASE_VERSION")
        or os.getenv("RENDER_GIT_COMMIT")
        or None
    )


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if not raw:
        return default
    try:
        return float(raw)
    except ValueError:
        logger.warning("%s=%r is not a float; using %s", name, raw, default)
        return default


# Heuristic redaction. send_default_pii=False already strips most of the
# auto-captured fields, but a request body with email/password fields can
# still appear in handled exception captures (e.g. when FastAPI's request
# validation reports the offending payload). Strip the obvious ones here.
_PII_KEYS = {
    "password",
    "passwd",
    "secret",
    "token",
    "api_key",
    "authorization",
    "cookie",
    "stripe_signature",
    "credit_card",
    "card_number",
    "cvv",
}


def _redact_event(event, hint):
    """before_send hook to redact obvious PII before shipping to Sentry."""
    try:
        request = (event or {}).get("request") or {}
        # Headers
        headers = request.get("headers") or {}
        for key in list(headers.keys()):
            if key.lower() in _PII_KEYS or "auth" in key.lower():
                headers[key] = "[redacted]"
        # Body data (FastAPI sometimes attaches request bodies to handled
        # validation errors). Walk one level.
        data = request.get("data") or {}
        if isinstance(data, dict):
            for key in list(data.keys()):
                if any(token in key.lower() for token in _PII_KEYS):
                    data[key] = "[redacted]"
    except Exception:  # noqa: BLE001 — never let a redactor break the SDK
        pass
    return event
