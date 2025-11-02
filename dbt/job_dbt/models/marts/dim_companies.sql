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
        company,
        company_size,
        source,
        first_seen_at
    FROM {{ source('staging', 'job_postings_stg') }}
    WHERE company IS NOT NULL
),

company_ranked AS (
    SELECT
        company,
        company_size,
        source,
        first_seen_at,
        ROW_NUMBER() OVER (
            PARTITION BY company 
            ORDER BY first_seen_at ASC
        ) AS rn
    FROM staging_jobs
),

deduped AS (
    SELECT
        company,
        company_size,
        source AS source_first_seen,
        first_seen_at AS created_at
    FROM company_ranked
    WHERE rn = 1
)

SELECT
    -- Surrogate key (using hash of normalized company name)
    MD5(LOWER({{ normalize_ws('deduped.company') }})) AS company_id,
    
    -- Natural attributes
    deduped.company,
    deduped.company_size,
    
    -- Metadata
    deduped.source_first_seen,
    deduped.created_at
FROM deduped
ORDER BY created_at DESC

