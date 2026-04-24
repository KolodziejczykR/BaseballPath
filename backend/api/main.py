from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ml.ml_router import router as ml_router
from api.routers.waitlist import router as waitlist_router
from api.routers.account import router as account_router
from api.routers.evaluations import router as evaluations_router
from api.routers.billing import router as billing_router
from api.routers.goals import router as goals_router
from api.routers.saved_schools import router as saved_schools_router

app = FastAPI(title="BaseballPath Backend")

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

app.include_router(ml_router, prefix="/predict")
app.include_router(waitlist_router, prefix="/waitlist")
app.include_router(account_router, prefix="/account")
app.include_router(evaluations_router, prefix="/evaluations")
app.include_router(billing_router, prefix="/billing")
app.include_router(goals_router, prefix="/goals", tags=["goals"])
app.include_router(saved_schools_router, prefix="/saved-schools", tags=["saved-schools"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the BaseballPath!"}

@app.get("/ping")
def health_check():
    return {"status": "ok"}

