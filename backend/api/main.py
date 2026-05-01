"""FastAPI application entrypoint.

Order of operations matters in this file:
  1. Path setup (so 'backend.x' imports resolve when uvicorn loads us).
  2. Sentry init BEFORE any route imports — if Sentry isn't up first, the
     import-time errors that break a deploy go untraced.
  3. Router imports + app construction.
  4. Middleware, exception handlers, and route mounting.
"""

import logging
import os
import sys

# 1. Path setup — must be before backend.* imports.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# 2. Sentry init — before any other backend import that could raise.
from backend.observability import init_sentry  # noqa: E402

init_sentry()

# 3. Standard imports + routers.
import sentry_sdk  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from slowapi import _rate_limit_exceeded_handler  # noqa: E402
from slowapi.errors import RateLimitExceeded  # noqa: E402

from api.rate_limit import limiter  # noqa: E402
from ml.ml_router import router as ml_router  # noqa: E402
from api.routers.waitlist import router as waitlist_router  # noqa: E402
from api.routers.account import router as account_router  # noqa: E402
from api.routers.evaluations import router as evaluations_router  # noqa: E402
from api.routers.billing import router as billing_router  # noqa: E402
from api.routers.goals import router as goals_router  # noqa: E402
from api.routers.saved_schools import router as saved_schools_router  # noqa: E402
from api.routers.feedback import router as feedback_router  # noqa: E402
from api.routers.health import router as health_router  # noqa: E402


logger = logging.getLogger(__name__)


app = FastAPI(title="BaseballPath Backend")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS middleware for frontend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://baseballpath.com",
        "https://www.baseballpath.com",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 4. Global exception handler. FastAPI's HTTPException handler still fires
# first for routes that raise HTTPException explicitly — this only catches
# uncaught exceptions that would otherwise leak a stack trace to the user.
# Sentry's FastAPI integration auto-captures the exception via middleware
# before this handler runs, so we don't double-send via capture_exception.
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception(
        "Unhandled exception in %s %s: %s",
        request.method,
        request.url.path,
        exc,
    )
    # Defense-in-depth: if Sentry's middleware integration didn't catch
    # this for some reason (it auto-instruments most cases), still ship
    # the event so we don't lose it.
    if sentry_sdk.is_initialized():
        sentry_sdk.capture_exception(exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"},
    )


app.include_router(health_router, tags=["health"])
app.include_router(ml_router, prefix="/predict")
app.include_router(waitlist_router, prefix="/waitlist")
app.include_router(account_router, prefix="/account")
app.include_router(evaluations_router, prefix="/evaluations")
app.include_router(billing_router, prefix="/billing")
app.include_router(goals_router, prefix="/goals", tags=["goals"])
app.include_router(saved_schools_router, prefix="/saved-schools", tags=["saved-schools"])
app.include_router(feedback_router, prefix="/feedback", tags=["feedback"])


@app.get("/")
def read_root():
    return {"message": "Welcome to the BaseballPath!"}
