{{
    config(
        materialized='incremental',
        schema='marts',
        unique_key='hash_key'
    )
}}

/*
    Job postings fact table with rankings.
    
    This model:
    - Contains all job postings with hash_key as unique identifier
    - Links to companies via company_id foreign key
    - Includes standardized fields for title, location, salary, etc.
    - Stores rank_score and rank_explain for job ranking (computed by ranker service)
    - Tracks ingestion timestamps
    
    For MVP, this is populated from staging and will be enriched/ranked
    by the enricher and ranker services in later steps.
*/

WITH staging AS (
    SELECT
        hash_key,
        job_title,
        company,
        location,
        remote_type,
        contract_type,
        seniority_level,
        salary_min,
        salary_max,
        salary_currency,
        skills_raw,
        posted_at,
        source,
        first_seen_at,
        last_seen_at,
        apply_url,
        -- Compute normalized company name and company_id to match dim_companies
        -- Handle NULL companies by using 'unknown' as default
        MD5(LOWER(REGEXP_REPLACE(TRIM(COALESCE(company, 'unknown')), '\s+', ' ', 'g'))) AS company_id_normalized
    FROM {{ source('staging', 'job_postings_stg') }}

    {% if is_incremental() %}
    WHERE first_seen_at > (
        SELECT
            COALESCE(MAX(ingested_at), '1900-01-01'::timestamptz)
        FROM {{ this }}
    )
    {% endif %}
    
),

companies AS (
    SELECT
        company_id,
        company
    FROM {{ ref('dim_companies') }}
)

SELECT
    -- Primary key and natural key
    staging.hash_key,
    
    -- Dimensions (standardized fields)
    staging.job_title AS job_title_std,  -- Will be enriched later
    COALESCE(companies.company_id, staging.company_id_normalized) AS company_id,
    staging.location AS location_std,  -- Will be enriched later
    staging.remote_type,
    staging.contract_type,
    staging.seniority_level,
    
    -- Normalized salary fields (will be enriched later)
    staging.salary_min AS salary_min_norm,
    staging.salary_max AS salary_max_norm,
    staging.salary_currency AS salary_currency_norm,
    
    -- Skills array (will be enriched later)
    staging.skills_raw AS skills,
    
    -- Timestamps
    staging.posted_at,
    staging.source,
    staging.first_seen_at AS ingested_at,
    staging.last_seen_at,
    
    -- Apply URL
    staging.apply_url,
    
    -- Ranking fields (populated by ranker service)
    -- Preserve existing rank_score and rank_explain during incremental runs
    {% if is_incremental() %}
    existing.rank_score,
    existing.rank_explain
    {% else %}
    NULL::NUMERIC AS rank_score,  -- Will be computed by ranker
    NULL::JSONB AS rank_explain  -- Will be computed by ranker
    {% endif %}
    
FROM staging
LEFT JOIN companies ON staging.company_id_normalized = companies.company_id
{% if is_incremental() %}
LEFT JOIN {{ this }} AS existing ON staging.hash_key = existing.hash_key
{% endif %}
ORDER BY staging.first_seen_at DESC

