{{
    config(
        materialized='incremental',
        unique_key='hash_key',
        on_schema_change='fail'
    )
}}

/*
    Staging model for job postings.
    
    This model:
    - Extracts fields from raw JSONB payloads
    - Normalizes data types and handles nulls
    - Calculates hash_key for deduplication (md5 of company|title|location)
    - Tracks first_seen_at and last_seen_at for each unique posting
    - Uses incremental strategy to efficiently handle new data
    
    The hash_key is our primary deduplication key:
    hash_key = md5(lower(company) || '|' || lower(title) || '|' || lower(location))
*/

WITH raw_data AS (
    SELECT
        raw_id,
        source,
        payload,
        collected_at
    FROM {{ source('raw', 'job_postings_raw') }}
    {% if is_incremental() %}
    -- Only process new records on incremental runs
    WHERE collected_at > (SELECT MAX(last_seen_at) FROM {{ this }})
    {% endif %}
),

extracted AS (
    SELECT
        raw_id,
        source,
        collected_at,
        
        -- Extract fields from JSONB payload
        -- Using ->> for text extraction, adjust paths based on actual API structure
        NULLIF(TRIM(payload->>'provider_job_id'), '')::TEXT AS provider_job_id,
        NULLIF(TRIM(payload->>'job_link'), '')::TEXT AS job_link,
        NULLIF(TRIM(payload->>'job_title'), '')::TEXT AS job_title,
        NULLIF(TRIM(payload->>'company'), '')::TEXT AS company,
        NULLIF(TRIM(payload->>'location'), '')::TEXT AS location,
        
        -- Enums with defaults to 'unknown'
        COALESCE(NULLIF(TRIM(payload->>'company_size'), ''), 'unknown')::TEXT AS company_size,
        COALESCE(NULLIF(LOWER(TRIM(payload->>'remote_type')), ''), 'unknown')::TEXT AS remote_type,
        COALESCE(NULLIF(LOWER(TRIM(payload->>'contract_type')), ''), 'unknown')::TEXT AS contract_type,
        
        -- Numeric salary fields
        NULLIF(payload->>'salary_min', '')::NUMERIC AS salary_min,
        NULLIF(payload->>'salary_max', '')::NUMERIC AS salary_max,
        NULLIF(TRIM(payload->>'salary_currency'), '')::TEXT AS salary_currency,
        
        -- Text fields
        NULLIF(TRIM(payload->>'description'), '')::TEXT AS description,
        NULLIF(TRIM(payload->>'apply_url'), '')::TEXT AS apply_url,
        
        -- Array field for skills (if provided by source)
        CASE 
            WHEN payload->'skills_raw' IS NOT NULL 
            THEN ARRAY(
                SELECT NULLIF(TRIM(value::TEXT, '"'), '')
                FROM jsonb_array_elements_text(payload->'skills_raw') AS value
                WHERE NULLIF(TRIM(value::TEXT, '"'), '') IS NOT NULL
            )
            ELSE NULL
        END AS skills_raw,
        
        -- Timestamp field
        NULLIF(payload->>'posted_at', '')::TIMESTAMPTZ AS posted_at
        
    FROM raw_data
),

with_hash AS (
    SELECT
        *,
        -- Calculate hash_key for deduplication
        -- This is the unique identifier: md5(company|title|location)
        -- normalize_ws() ensures "Acme Corp" and "Acme  Corp" (double space) are treated identically
        MD5(
            LOWER({{ normalize_ws('COALESCE(company, \'\')') }}) || '|' || 
            LOWER({{ normalize_ws('COALESCE(job_title, \'\')') }}) || '|' || 
            LOWER({{ normalize_ws('COALESCE(location, \'\')') }})
        ) AS hash_key
    FROM extracted
    WHERE company IS NOT NULL 
      AND job_title IS NOT NULL 
      AND location IS NOT NULL
),

existing_records AS (
    {% if is_incremental() %}
    -- Get existing records to preserve first_seen_at timestamps
    -- This runs once, not once per row (much more efficient!)
    SELECT 
        hash_key,
        first_seen_at
    FROM {{ this }}
    {% else %}
    -- On full refresh, no existing records to preserve
    SELECT 
        NULL::TEXT AS hash_key,
        NULL::TIMESTAMPTZ AS first_seen_at
    WHERE FALSE
    {% endif %}
)

SELECT
    with_hash.hash_key,
    with_hash.provider_job_id,
    with_hash.job_link,
    with_hash.job_title,
    with_hash.company,
    with_hash.company_size,
    with_hash.location,
    with_hash.remote_type,
    with_hash.contract_type,
    with_hash.salary_min,
    with_hash.salary_max,
    with_hash.salary_currency,
    with_hash.description,
    with_hash.skills_raw,
    with_hash.posted_at,
    with_hash.apply_url,
    with_hash.source,
    
    -- Track when we first and last saw this posting
    -- If the record exists, preserve first_seen_at; otherwise use current collected_at
    COALESCE(existing_records.first_seen_at, with_hash.collected_at) AS first_seen_at,
    with_hash.collected_at AS last_seen_at
    
FROM with_hash
LEFT JOIN existing_records ON with_hash.hash_key = existing_records.hash_key

