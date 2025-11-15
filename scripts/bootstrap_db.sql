-- Job-ETL Database Bootstrap Script
-- This script sets up the initial database structure for the Job-ETL project

-- Create the main database if it doesn't exist
-- Note: This is typically handled by the POSTGRES_DB environment variable

-- Create schemas
CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS marts;

-- Grant permissions to the job_etl_user
GRANT ALL PRIVILEGES ON SCHEMA raw TO job_etl_user;
GRANT ALL PRIVILEGES ON SCHEMA staging TO job_etl_user;
GRANT ALL PRIVILEGES ON SCHEMA marts TO job_etl_user;

-- Create extensions that might be needed
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Create the raw.job_postings_raw table
CREATE TABLE IF NOT EXISTS raw.job_postings_raw (
    raw_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    source TEXT NOT NULL,
    payload JSONB NOT NULL,
    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_raw_job_postings_collected_at ON raw.job_postings_raw(collected_at);
CREATE INDEX IF NOT EXISTS idx_raw_job_postings_source ON raw.job_postings_raw(source);
CREATE INDEX IF NOT EXISTS idx_raw_job_postings_payload_gin ON raw.job_postings_raw USING GIN(payload);

-- Grant permissions on the table
GRANT ALL PRIVILEGES ON TABLE raw.job_postings_raw TO job_etl_user;

-- Create staging table populated by the Python normalizer service
CREATE TABLE IF NOT EXISTS staging.job_postings_stg (
    provider_job_id TEXT,
    job_link TEXT,
    job_title TEXT,
    company TEXT,
    company_size TEXT,
    location TEXT,
    remote_type TEXT CHECK (remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
    contract_type TEXT CHECK (contract_type IN ('full_time', 'part_time', 'contract', 'intern', 'temp', 'unknown')),
    seniority_level TEXT CHECK (seniority_level IN ('junior', 'intermediate', 'senior', 'unknown')) DEFAULT 'unknown',
    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_currency TEXT,
    description TEXT,
    skills_raw TEXT[],
    posted_at TIMESTAMPTZ,
    apply_url TEXT,
    source TEXT,
    hash_key TEXT PRIMARY KEY,
    first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for staging table
-- Note: hash_key already has an index as PRIMARY KEY, so no separate index needed
CREATE INDEX IF NOT EXISTS idx_staging_job_postings_source ON staging.job_postings_stg(source);
CREATE INDEX IF NOT EXISTS idx_staging_job_postings_company ON staging.job_postings_stg(company);
CREATE INDEX IF NOT EXISTS idx_staging_job_postings_posted_at ON staging.job_postings_stg(posted_at);

-- Grant permissions on staging table
GRANT ALL PRIVILEGES ON TABLE staging.job_postings_stg TO job_etl_user;

-- Create marts tables (populated by dbt models during the dbt_models_core task)
CREATE TABLE IF NOT EXISTS marts.dim_companies (
    company_id SERIAL PRIMARY KEY,
    company TEXT NOT NULL,
    company_size TEXT,
    source_first_seen TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS marts.fact_jobs (
    job_id SERIAL PRIMARY KEY,
    hash_key TEXT UNIQUE NOT NULL,
    job_title_std TEXT,
    company_id INTEGER REFERENCES marts.dim_companies(company_id),
    location_std TEXT,
    location_lat NUMERIC,
    location_lon NUMERIC,
    remote_type TEXT CHECK (remote_type IN ('remote', 'hybrid', 'onsite', 'unknown')),
    contract_type TEXT CHECK (contract_type IN ('full_time', 'part_time', 'contract', 'intern', 'temp', 'unknown')),
    seniority_level TEXT,
    salary_min_norm NUMERIC,
    salary_max_norm NUMERIC,
    salary_currency_norm TEXT DEFAULT 'CAD',
    skills TEXT[],
    posted_at TIMESTAMPTZ,
    source TEXT,
    apply_url TEXT,
    rank_score NUMERIC,
    rank_explain JSONB,
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Create indexes for marts tables
CREATE INDEX IF NOT EXISTS idx_fact_jobs_hash_key ON marts.fact_jobs(hash_key);
CREATE INDEX IF NOT EXISTS idx_fact_jobs_rank_score ON marts.fact_jobs(rank_score DESC);
CREATE INDEX IF NOT EXISTS idx_fact_jobs_company_id ON marts.fact_jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_fact_jobs_posted_at ON marts.fact_jobs(posted_at);

-- Grant permissions on marts tables
GRANT ALL PRIVILEGES ON TABLE marts.dim_companies TO job_etl_user;
GRANT ALL PRIVILEGES ON TABLE marts.fact_jobs TO job_etl_user;
GRANT ALL PRIVILEGES ON SEQUENCE marts.dim_companies_company_id_seq TO job_etl_user;
GRANT ALL PRIVILEGES ON SEQUENCE marts.fact_jobs_job_id_seq TO job_etl_user;

-- Create a function to generate hash_key (for deduplication)
CREATE OR REPLACE FUNCTION generate_hash_key(
    company_name TEXT,
    job_title TEXT,
    location_name TEXT
) RETURNS TEXT AS $$
BEGIN
    RETURN encode(digest(
        lower(trim(regexp_replace(company_name, '\s+', ' ', 'g'))) || '|' ||
        lower(trim(regexp_replace(job_title, '\s+', ' ', 'g'))) || '|' ||
        lower(trim(regexp_replace(location_name, '\s+', ' ', 'g'))),
        'md5'
    ), 'hex');
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION generate_hash_key(TEXT, TEXT, TEXT) TO job_etl_user;

-- Create a view for easy access to job posting statistics
CREATE OR REPLACE VIEW marts.job_posting_stats AS
SELECT 
    source,
    COUNT(*) as total_postings,
    COUNT(DISTINCT hash_key) as unique_postings,
    MIN(posted_at) as earliest_posting,
    MAX(posted_at) as latest_posting,
    COUNT(*) FILTER (WHERE rank_score IS NOT NULL) as ranked_postings,
    AVG(rank_score) as avg_rank_score
FROM marts.fact_jobs
GROUP BY source;

-- Grant permissions on the view
GRANT SELECT ON marts.job_posting_stats TO job_etl_user;

-- Insert some sample data for testing (optional)
-- Note: Only insert test data if in development environment
-- In production, remove this section or use a separate seed file
-- INSERT INTO raw.job_postings_raw (source, payload) VALUES 
-- ('sample', '{"title": "Data Engineer", "company": "Sample Corp", "location": "Montreal, QC"}')
-- ON CONFLICT DO NOTHING;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Job-ETL database bootstrap completed successfully';
    RAISE NOTICE 'Schemas created: raw, staging, marts';
    RAISE NOTICE 'Tables created with proper indexes and constraints';
    RAISE NOTICE 'Permissions granted to job_etl_user';
END $$;

