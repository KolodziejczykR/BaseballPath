from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import sys
import os

# Add the backend directory to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.waitlist_router import router as waitlist_router

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

# Include only the waitlist router for now
app.include_router(waitlist_router, prefix="/waitlist")

@app.get("/")
def read_root():
    return {"message": "Welcome to the BaseballPATH!"}

@app.get("/ping")
def health_check():
    return {"status": "ok"}