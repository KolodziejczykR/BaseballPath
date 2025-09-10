#!/bin/bash
# Render startup script for FastAPI
uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}