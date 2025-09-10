#!/bin/bash
# Render startup script for FastAPI
uvicorn api.main_waitlist:app --host 0.0.0.0 --port ${PORT:-8000}