from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.ml.ml_router import router as ml_router
from backend.ml.router.infielder_router import router as infielder_router
from backend.ml.router.outfielder_router import router as outfielder_router
from backend.ml.router.catcher_router import router as catcher_router
from backend.api.preferences_router import router as preferences_router
from backend.api.college_selection_router import router as college_selection_router
from backend.api.waitlist_router import router as waitlist_router

app = FastAPI(title="BaseballPATH Backend")

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001", 
        "https://baseballpath.com",
        "https://www.baseballpath.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include the ML routers
app.include_router(ml_router, prefix="/predict")
app.include_router(infielder_router, prefix="/infielder")
app.include_router(outfielder_router, prefix="/outfielder")
app.include_router(catcher_router, prefix="/catcher")
app.include_router(preferences_router, prefix="/preferences")
app.include_router(college_selection_router, prefix="/college-selection")
app.include_router(waitlist_router, prefix="/waitlist")

@app.get("/")
def read_root():
    return {"message": "Welcome to the BaseballPATH!"}

@app.get("/ping")
def health_check():
    return {"status": "ok"}

# Placeholder for future router imports