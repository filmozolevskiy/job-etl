-- Migration: Add staging.companies_stg table for company enrichment
-- This migration adds the companies_stg table that was added to bootstrap_db.sql
-- Run this if your database was initialized before the companies_stg table was added

-- Create staging.companies_stg table for enriched company data from Glassdoor API
CREATE TABLE IF NOT EXISTS staging.companies_stg (
    company_id TEXT PRIMARY KEY,  -- Our existing MD5 hash
    glassdoor_company_id INTEGER,  -- Glassdoor's company_id from API
    name TEXT,  -- Company name from API
    company_link TEXT,
    rating NUMERIC,
    review_count INTEGER,
    salary_count INTEGER,
    job_count INTEGER,
    headquarters_location TEXT,
    logo TEXT,
    company_size TEXT,
    company_size_category TEXT,
    company_description TEXT,
    industry TEXT,
    website TEXT,
    company_type TEXT,
    revenue TEXT,
    business_outlook_rating NUMERIC,
    career_opportunities_rating NUMERIC,
    ceo TEXT,
    ceo_rating NUMERIC,
    compensation_and_benefits_rating NUMERIC,
    culture_and_values_rating NUMERIC,
    diversity_and_inclusion_rating NUMERIC,
    recommend_to_friend_rating NUMERIC,
    senior_management_rating NUMERIC,
    work_life_balance_rating NUMERIC,
    stock TEXT,
    year_founded INTEGER,
    reviews_link TEXT,
    jobs_link TEXT,
    faq_link TEXT,
    competitors JSONB,  -- Array of competitor objects
    office_locations JSONB,  -- Array of location objects
    best_places_to_work_awards JSONB,  -- Array of award objects
    source_first_seen TEXT,  -- First source where this company was observed
    enriched_at TIMESTAMPTZ,  -- When API data was fetched (NULL if not enriched)
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),  -- When record was created
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()  -- When record was last updated
);

-- Create indexes for companies_stg table
CREATE INDEX IF NOT EXISTS idx_companies_stg_glassdoor_id ON staging.companies_stg(glassdoor_company_id);
CREATE INDEX IF NOT EXISTS idx_companies_stg_name ON staging.companies_stg(name);

-- Grant permissions on companies_stg table
GRANT ALL PRIVILEGES ON TABLE staging.companies_stg TO job_etl_user;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration completed: staging.companies_stg table created';
END $$;

