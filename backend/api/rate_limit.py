"""Shared SlowAPI rate limiter.

Defined in its own module so routers can import the decorator without
circular-importing ``api.main``. The limiter is keyed by client IP via
SlowAPI's ``get_remote_address`` helper, which respects the
``X-Forwarded-For`` header that Render and other load balancers set.

Storage backend:
  - Default ``memory://`` works for single-process deployments and dev.
  - For multi-worker / multi-instance prod, set
    ``RATE_LIMIT_STORAGE_URI=redis://...`` so the same IP can't bypass
    the limit by hitting a different worker.

Per-route limits live with the route itself via ``@limiter.limit("...")``;
the global default is empty so opt-in is explicit.
"""

import os

from slowapi import Limiter
from slowapi.util import get_remote_address


limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=os.getenv("RATE_LIMIT_STORAGE_URI", "memory://"),
    default_limits=[],
)
