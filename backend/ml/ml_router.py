from fastapi import APIRouter


# Import the position-specific routers
from .router.infielder_router import router as infielder_router
from .router.outfielder_router import router as outfielder_router
from .router.catcher_router import router as catcher_router
from .router.pitcher_router import router as pitcher_router

router = APIRouter()

# Include the position-specific routers
router.include_router(infielder_router, prefix="/infielder", tags=["infielder"])
router.include_router(outfielder_router, prefix="/outfielder", tags=["outfielder"])
router.include_router(catcher_router, prefix="/catcher", tags=["catcher"])
router.include_router(pitcher_router, prefix="/pitcher", tags=["pitcher"])
