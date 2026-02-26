Example Setup
- From the root Code directory...
- Install Python deps: `pip install -r backend/requirements.txt`
- Install Redis (macOS): `brew install redis`
- Start Redis (background): `brew services start redis`
- Start Celery worker (project root): `celery -A backend.llm.tasks.celery_app worker --loglevel=info`
- Run example: `python3 backend/examples/run_full_recommendation_pipeline.py`

Notes
- Redis must be running for queued LLM reasoning.
  - To check if it is running, run `brew services list`
- If you prefer foreground Redis: `redis-server`
- Verify Redis: `redis-cli ping` (should return `PONG`)
- Optional env vars:
  - `CELERY_BROKER_URL=redis://localhost:6379/0`
  - `CELERY_RESULT_BACKEND=redis://localhost:6379/1`
  - `OPENAI_API_KEY=...`

Load Test
- Terminal 1 — Start Redis (background): `brew services start redis`
- Terminal 2 — Start Celery worker (project root): `celery -A backend.llm.tasks.celery_app worker --loglevel=info`
- Terminal 3 — Start API server: `uvicorn backend.api.main:app --reload --port 8000`
- Terminal 4 — Run basic load test (LLM off): `python3 backend/examples/load_test_preferences.py --total 50 --concurrency 10`
- Terminal 4 — Run basic load test (LLM on, queues only): `python3 backend/examples/load_test_preferences.py --total 50 --concurrency 10 --use-llm`

Cache/Dedup Verification
- Run the same request twice with `use_llm_reasoning=true`
  - First request should return `llm_status: queued` and a `llm_job_id`
  - Second request should return either:
    - `llm_status: queued` with the same `llm_job_id` (in-flight dedup), or
    - `llm_status: cached` with a cache key
- Example (same payload twice):
  - `curl -X POST http://localhost:8000/preferences/filter -H "Content-Type: application/json" -d @payload.json`
  - Repeat the same command and compare `recommendation_summary.llm_job_id` and `llm_status`
