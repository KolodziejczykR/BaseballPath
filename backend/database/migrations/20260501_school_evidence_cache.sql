-- Cache of position-agnostic, parsed school roster + stats.
-- Populated weekly by backend/scripts/refresh_school_evidence_cache.py.
-- Read by the deep-school-research Celery worker (in service.py) in lieu
-- of live HTML fetching. Live-fetch fallback preserved for misses/stale.

CREATE TABLE IF NOT EXISTS school_evidence_cache (
    school_name      TEXT PRIMARY KEY,
    roster_url       TEXT,
    matched_players  JSONB NOT NULL,
    stats_available  BOOLEAN NOT NULL DEFAULT false,
    source_status    TEXT NOT NULL,
    error_message    TEXT,
    fetched_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_school_evidence_cache_fetched_at
    ON school_evidence_cache(fetched_at);

ALTER TABLE school_evidence_cache ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Enable all operations for service role" ON school_evidence_cache
    FOR ALL USING (auth.role() = 'service_role');
