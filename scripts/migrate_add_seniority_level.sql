-- Migration Script: Add seniority_level to staging and marts tables
-- This script:
-- 1. Adds seniority_level column to staging.job_postings_stg (if not exists)
-- 2. Adds seniority_level column to marts.fact_jobs (if not exists)
-- 3. Backfills seniority_level for existing records based on job_title

-- Step 1: Add column to staging table (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'staging' 
        AND table_name = 'job_postings_stg' 
        AND column_name = 'seniority_level'
    ) THEN
        ALTER TABLE staging.job_postings_stg 
        ADD COLUMN seniority_level TEXT CHECK (seniority_level IN ('junior', 'intermediate', 'senior', 'unknown')) DEFAULT 'unknown';
        
        RAISE NOTICE 'Added seniority_level column to staging.job_postings_stg';
    ELSE
        RAISE NOTICE 'Column seniority_level already exists in staging.job_postings_stg';
    END IF;
END $$;

-- Step 2: Add column to marts.fact_jobs (if not exists)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'marts' 
        AND table_name = 'fact_jobs' 
        AND column_name = 'seniority_level'
    ) THEN
        ALTER TABLE marts.fact_jobs 
        ADD COLUMN seniority_level TEXT;
        
        RAISE NOTICE 'Added seniority_level column to marts.fact_jobs';
    ELSE
        RAISE NOTICE 'Column seniority_level already exists in marts.fact_jobs';
    END IF;
END $$;

-- Step 3: Create function to extract seniority from job title (SQL version)
-- This mirrors the Python extraction logic
CREATE OR REPLACE FUNCTION extract_seniority_from_title(job_title TEXT) 
RETURNS TEXT AS $$
DECLARE
    title_lower TEXT;
BEGIN
    IF job_title IS NULL OR job_title = '' THEN
        RETURN 'unknown';
    END IF;
    
    title_lower := LOWER(job_title);
    
    -- Check for Roman numeral levels first (I, II, III)
    -- Level I = Junior, Level II = Intermediate, Level III = Senior
    -- Check III first to avoid matching II or I within it
    -- Patterns: "Engineer III", "Level III", "III", " iii ", etc.
    IF title_lower LIKE '% iii%' OR 
       title_lower LIKE 'iii%' OR 
       title_lower LIKE '%level iii%' OR
       title_lower LIKE '% iii,%' OR
       title_lower LIKE '% iii)%' OR
       title_lower LIKE '% iii/%' OR
       title_lower LIKE '% iii' THEN
        RETURN 'senior';
    END IF;
    -- Patterns: "Engineer II", "Level II", "II", " ii ", etc.
    -- Note: "Engineer II" has no space before II, so check for that pattern
    IF title_lower LIKE '% ii %' OR 
       title_lower LIKE 'ii %' OR 
       title_lower LIKE '%level ii%' OR
       title_lower LIKE '% ii,%' OR
       title_lower LIKE '% ii)%' OR
       title_lower LIKE '% ii/%' OR
       title_lower LIKE '% ii' OR
       title_lower LIKE '%engineer ii%' THEN
        RETURN 'intermediate';
    END IF;
    -- Patterns: "Engineer I", "Level I", "I", " i ", etc.
    -- Be careful with single "i" - only match if it's clearly a level indicator
    IF title_lower LIKE '%level i%' OR
       title_lower LIKE '% i %' OR 
       title_lower LIKE 'i %' OR
       title_lower LIKE '% i,%' OR
       title_lower LIKE '% i)%' OR
       title_lower LIKE '% i/%' OR
       title_lower LIKE '% i' OR
       title_lower LIKE '%engineer i %' OR
       title_lower LIKE '%engineer i)%' THEN
        RETURN 'junior';
    END IF;
    
    -- Check for numeric/letter levels (L4, L5, L6, etc.)
    -- L4 = Intermediate, L5+ = Senior
    -- Using word boundary \y for PostgreSQL
    IF title_lower ~ '\yL[5-9]\y' OR title_lower ~ '\yL[1-9][0-9]+\y' THEN
        RETURN 'senior';
    END IF;
    IF title_lower ~ '\yL4\y' THEN
        RETURN 'intermediate';
    END IF;
    
    -- Check for other seniority indicators
    IF title_lower LIKE '%advanced%' OR
       title_lower LIKE '%director%' OR
       title_lower LIKE '%manager%' OR
       title_lower LIKE '%vp%' OR
       title_lower LIKE '%vice president%' OR
       title_lower LIKE '%head of%' THEN
        RETURN 'senior';
    END IF;
    
    IF title_lower LIKE '%intern%' THEN
        RETURN 'junior';
    END IF;
    
    -- Check for senior indicators (check more specific first)
    -- Using substring matching to match Python behavior exactly
    -- Python uses: any(keyword in job_title_lower for keyword in keywords)
    -- This matches if the keyword appears anywhere in the string
    IF title_lower LIKE '%senior%' OR
       title_lower LIKE '%principal%' OR
       title_lower LIKE '%staff%' OR
       title_lower LIKE '%architect%' OR
       title_lower LIKE '%lead%' OR
       title_lower LIKE '% sr %' OR title_lower LIKE 'sr %' OR title_lower LIKE '% sr' OR title_lower = 'sr' THEN
        RETURN 'senior';
    END IF;
    
    -- Check for intermediate indicators
    IF title_lower LIKE '%intermediate%' OR
       title_lower LIKE '%mid-level%' OR
       title_lower LIKE '%mid level%' OR
       title_lower LIKE '% mid %' OR title_lower LIKE 'mid %' OR title_lower LIKE '% mid' OR title_lower = 'mid' THEN
        RETURN 'intermediate';
    END IF;
    
    -- Check for junior indicators
    IF title_lower LIKE '%junior%' OR
       title_lower LIKE '%associate%' OR
       title_lower LIKE '%entry-level%' OR
       title_lower LIKE '%entry level%' OR
       title_lower LIKE '%entry%' OR
       title_lower LIKE '% jr %' OR title_lower LIKE 'jr %' OR title_lower LIKE '% jr' OR title_lower = 'jr' THEN
        RETURN 'junior';
    END IF;
    
    -- No indicators found
    RETURN 'unknown';
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Step 4: Backfill staging table
-- Re-run extraction on all records to catch previously missed matches (principal, staff, lead)
UPDATE staging.job_postings_stg
SET seniority_level = extract_seniority_from_title(job_title);

-- Step 5: Backfill marts.fact_jobs from staging
UPDATE marts.fact_jobs fj
SET seniority_level = stg.seniority_level
FROM staging.job_postings_stg stg
WHERE fj.hash_key = stg.hash_key
  AND (fj.seniority_level IS NULL OR fj.seniority_level != stg.seniority_level);

-- Step 6: Set default for any remaining NULL values
UPDATE staging.job_postings_stg
SET seniority_level = 'unknown'
WHERE seniority_level IS NULL;

UPDATE marts.fact_jobs
SET seniority_level = 'unknown'
WHERE seniority_level IS NULL;

-- Step 7: Display summary statistics
DO $$
DECLARE
    staging_total INTEGER;
    staging_junior INTEGER;
    staging_intermediate INTEGER;
    staging_senior INTEGER;
    staging_unknown INTEGER;
    fact_total INTEGER;
    fact_junior INTEGER;
    fact_intermediate INTEGER;
    fact_senior INTEGER;
    fact_unknown INTEGER;
BEGIN
    -- Staging statistics
    SELECT COUNT(*) INTO staging_total FROM staging.job_postings_stg;
    SELECT COUNT(*) INTO staging_junior FROM staging.job_postings_stg WHERE seniority_level = 'junior';
    SELECT COUNT(*) INTO staging_intermediate FROM staging.job_postings_stg WHERE seniority_level = 'intermediate';
    SELECT COUNT(*) INTO staging_senior FROM staging.job_postings_stg WHERE seniority_level = 'senior';
    SELECT COUNT(*) INTO staging_unknown FROM staging.job_postings_stg WHERE seniority_level = 'unknown';
    
    -- Fact statistics
    SELECT COUNT(*) INTO fact_total FROM marts.fact_jobs;
    SELECT COUNT(*) INTO fact_junior FROM marts.fact_jobs WHERE seniority_level = 'junior';
    SELECT COUNT(*) INTO fact_intermediate FROM marts.fact_jobs WHERE seniority_level = 'intermediate';
    SELECT COUNT(*) INTO fact_senior FROM marts.fact_jobs WHERE seniority_level = 'senior';
    SELECT COUNT(*) INTO fact_unknown FROM marts.fact_jobs WHERE seniority_level = 'unknown';
    
    RAISE NOTICE '========================================';
    RAISE NOTICE 'Migration Summary: seniority_level';
    RAISE NOTICE '========================================';
    RAISE NOTICE 'staging.job_postings_stg:';
    RAISE NOTICE '  Total: %', staging_total;
    RAISE NOTICE '  Junior: %', staging_junior;
    RAISE NOTICE '  Intermediate: %', staging_intermediate;
    RAISE NOTICE '  Senior: %', staging_senior;
    RAISE NOTICE '  Unknown: %', staging_unknown;
    RAISE NOTICE '';
    RAISE NOTICE 'marts.fact_jobs:';
    RAISE NOTICE '  Total: %', fact_total;
    RAISE NOTICE '  Junior: %', fact_junior;
    RAISE NOTICE '  Intermediate: %', fact_intermediate;
    RAISE NOTICE '  Senior: %', fact_senior;
    RAISE NOTICE '  Unknown: %', fact_unknown;
    RAISE NOTICE '========================================';
END $$;

-- Grant execute permission on the function
GRANT EXECUTE ON FUNCTION extract_seniority_from_title(TEXT) TO job_etl_user;

-- Log completion
DO $$
BEGIN
    RAISE NOTICE 'Migration completed successfully';
    RAISE NOTICE 'All existing records have been backfilled with seniority_level';
END $$;

