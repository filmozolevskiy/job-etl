{{
    config(
        materialized='table',
        schema='marts'
    )
}}

/*
    Company dimension table with enriched data from Glassdoor API.
    
    This model:
    - Reads directly from staging.companies_stg (which contains both base and enriched data)
    - Creates surrogate key (company_id) for companies
    - Includes enriched data from Glassdoor API when available (rating, year_founded, etc.)
    
    Base company records are created by the enricher service from job_postings_stg,
    and then enriched with Glassdoor API data. This model reads the final result.
    
    This is a slowly changing dimension (SCD Type 1) where we keep the latest
    company information and overwrite previous values.
*/

SELECT
    company_id,
    COALESCE(name, 'unknown') AS company,
    rating,
    company_size,
    year_founded,
    company_type,
    company_link,
    compensation_and_benefits_rating,
    work_life_balance_rating,
    office_locations,
    source_first_seen,
    created_at
FROM {{ source('staging', 'companies_stg') }}
ORDER BY created_at DESC

