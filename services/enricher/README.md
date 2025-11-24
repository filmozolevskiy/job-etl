# Enricher Service

The enricher service enriches job postings with extracted skills and company information.

## Features

1. **Skills Extraction**: Extracts skills from job descriptions using spaCy and curated keyword dictionaries
2. **Company Enrichment**: Enriches company data by calling the Glassdoor API and using fuzzy matching

## Skills Extraction

The service reads job postings from `staging.job_postings_stg` that have descriptions but no skills, extracts skills using NLP techniques, and writes the results back to the same table.

### Skills Dictionary

Skills are extracted using a curated dictionary located at `config/taxonomy/skills_dictionary.yml`. The dictionary contains:
- Technical skills (programming languages, frameworks, tools)
- Soft skills
- Domain-specific keywords

### Usage

```bash
python -m services.enricher.main \
    --limit 100 \
    --source jsearch \
    --dictionary-path config/taxonomy/skills_dictionary.yml \
    --verbose
```

## Company Enrichment

The service enriches company information by:
1. Extracting unique company names from `staging.job_postings_stg`
2. Using fuzzy string matching to find companies in the Glassdoor API
3. Storing enriched data in `staging.companies_stg`
4. Making enriched fields available to downstream dbt models

### Fuzzy Matching

Company names are matched using the `rapidfuzz` library with an 80% similarity threshold. The matcher:
- Normalizes company names (removes common suffixes like "Inc.", "LLC", etc.)
- Compares normalized names using fuzzy string matching
- Returns the best match if similarity score >= 80%

### Glassdoor API

The service uses the OpenWebNinja Glassdoor API endpoint:
- Endpoint: `/realtime-glassdoor-data/company-search`
- Requires API key via `GLASSDOOR_API_KEY` environment variable or Airflow Variable
- Returns company information including ratings, size, year founded, office locations, etc.

### Usage

Company enrichment is enabled by default. To disable:

```bash
python -m services.enricher.main --no-enrich-companies
```

To specify API key explicitly:

```bash
python -m services.enricher.main --glassdoor-api-key YOUR_API_KEY
```

## Environment Variables

- `DATABASE_URL`: PostgreSQL connection string (required)
- `GLASSDOOR_API_KEY`: Glassdoor API key for company enrichment (optional, but required if enrichment enabled)
- `SKILLS_DICTIONARY_PATH`: Path to skills dictionary YAML file (optional, defaults to `config/taxonomy/skills_dictionary.yml`)

## Command-Line Arguments

- `--limit`: Maximum number of jobs to process
- `--source`: Filter to specific source(s) (can be provided multiple times)
- `--include-existing`: Reprocess rows that already contain skills
- `--dictionary-path`: Override path to skills_dictionary.yml
- `--dry-run`: Extract skills but do not persist updates
- `--verbose`: Enable debug logging
- `--enrich-companies`: Enable company enrichment (default: True)
- `--no-enrich-companies`: Disable company enrichment
- `--glassdoor-api-key`: Glassdoor API key (defaults to GLASSDOOR_API_KEY env var)

## Output

The service updates:
- `staging.job_postings_stg.skills_raw`: Array of extracted skills
- `staging.companies_stg`: Enriched company data from Glassdoor API

Downstream dbt models (`marts.dim_companies`) consume the enriched data.

## Error Handling

- API errors are logged but processing continues (no retries in the same run)
- Database errors cause the service to exit with error code 2
- Missing API key for company enrichment results in a warning and continues without enrichment

