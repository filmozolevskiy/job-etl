{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Company dimension table.
    
    This model:
    - Creates surrogate key (company_id) for companies
    - Normalizes company names
    - Tracks company size buckets
    - Records first source seen and creation timestamp
    
    This is a slowly changing dimension (SCD Type 1) where we keep the latest
    company information and overwrite previous values.
*/

WITH staging_jobs AS (
    SELECT DISTINCT
        COALESCE(company, 'unknown') AS company,
        company_size,
        source,
        first_seen_at
    FROM {{ source('staging', 'job_postings_stg') }}
),

-- Normalize company names and create company_id upfront
companies_with_id AS (
    SELECT
        company,
        company_size,
        source,
        first_seen_at,
        -- Generate company_id from normalized name (this ensures uniqueness)
        MD5(LOWER({{ normalize_ws('company') }})) AS company_id
    FROM staging_jobs
),

-- Deduplicate by company_id (normalized name) to ensure uniqueness
-- This handles cases where different raw names normalize to the same value
company_ranked AS (
    SELECT
        company_id,
        company,
        company_size,
        source,
        first_seen_at,
        ROW_NUMBER() OVER (
            PARTITION BY company_id 
            ORDER BY first_seen_at ASC
        ) AS rn
    FROM companies_with_id
),

deduped AS (
    SELECT
        company_id,
        -- Take the first company name seen (raw value for display)
        company,
        company_size,
        source AS source_first_seen,
        first_seen_at AS created_at
    FROM company_ranked
    WHERE rn = 1
)

SELECT
    -- Surrogate key (already computed and deduped)
    deduped.company_id,
    
    -- Natural attributes
    deduped.company,
    deduped.company_size,
    
    -- Metadata
    deduped.source_first_seen,
    deduped.created_at
FROM deduped
ORDER BY created_at DESC

