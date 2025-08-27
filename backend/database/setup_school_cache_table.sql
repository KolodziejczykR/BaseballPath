-- School Data Cache Table for BaseballPATH
-- Run this SQL in your Supabase SQL editor to create the caching table

CREATE TABLE IF NOT EXISTS school_data_cache (
    id SERIAL PRIMARY KEY,
    school_name TEXT UNIQUE NOT NULL,
    scorecard_data JSONB,
    niche_data JSONB,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on school_name for faster lookups
CREATE INDEX IF NOT EXISTS idx_school_data_cache_name ON school_data_cache(school_name);

-- Create index on updated_at for cache expiry checks  
CREATE INDEX IF NOT EXISTS idx_school_data_cache_updated ON school_data_cache(updated_at);

-- Enable Row Level Security (optional but recommended)
ALTER TABLE school_data_cache ENABLE ROW LEVEL SECURITY;

-- Create policy to allow service role full access (adjust as needed for your security requirements)
CREATE POLICY "Enable all operations for service role" ON school_data_cache
    FOR ALL USING (auth.role() = 'service_role');