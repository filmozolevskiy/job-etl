# Ranker Service

The ranker service calculates job ranking scores based on configurable weights and user profile preferences.

## Purpose

The ranker analyzes each job posting and assigns a score (0-100) based on how well it matches the user's preferences:

```
[Enricher] → marts.fact_jobs
         ↓
   [RANKER] ← You are here
         ↓
marts.fact_jobs (with rank_score & rank_explain)
         ↓
[Publisher] → Tableau
```

## Key Features

### 1. Configurable Scoring
- Reads weights and profile from `config/ranking.yml`
- Weights determine importance of different factors
- Profile defines user preferences

### 2. Transparent Explainability
- Stores `rank_explain` JSONB with per-feature subscores
- Shows why a job received its score
- Helps debug and tune ranking algorithm

### 3. Minimal Stub Implementation (MVP)
- Simple keyword-based scoring for title and skills
- Basic location, salary, and attribute matching
- Full algorithm implemented in Phase 1

## Architecture

```
ranker/
├── __init__.py           # Package initialization
├── scoring.py            # Core ranking algorithm
├── config_loader.py      # Load ranking.yml configuration
├── db_operations.py      # Database read/write operations
├── main.py              # CLI entry point
├── requirements.txt      # Python dependencies
└── README.md            # This file
```

### Component Responsibilities

**config_loader.py**
- Load and validate ranking.yml
- Parse weights and profile
- Default fallbacks for missing config

**scoring.py**
- Core ranking algorithm
- Calculate per-feature scores
- Combine into final rank_score

**db_operations.py**
- Fetch unranked jobs from marts.fact_jobs
- Update rank_score and rank_explain
- Batch processing support

**main.py**
- CLI interface
- Entry point for Airflow tasks
- Statistics and logging

## Scoring Algorithm (MVP)

For the minimal implementation, scoring is simplified:

1. **Title Keywords**: Simple substring matching
2. **Skills Overlap**: Basic set intersection
3. **Location**: Exact match (proximity in Phase 1)
4. **Salary**: Binary in-range check
5. **Remote Type**: Exact match to preferences
6. **Contract Type**: Exact match to preferences
7. **Seniority**: Simple keyword detection
8. **Company Size**: Exact match to preferences

Final score: `Σ(weight_i * feature_score_i) * 100`

## Usage

### From CLI

```bash
# Rank all unranked jobs
python -m services.ranker.main

# Specify config file
python -m services.ranker.main --config /path/to/ranking.yml

# Dry run (no database updates)
python -m services.ranker.main --dry-run
```

### From Python

```python
from services.ranker.db_operations import RankerDB
from services.ranker.config_loader import load_ranking_config
from services.ranker.scoring import calculate_rank

# Load configuration
config = load_ranking_config('config/ranking.yml')

# Connect to database
db = RankerDB('postgresql://...')

# Fetch unranked jobs
jobs = db.fetch_unranked_jobs()

# Calculate and update scores
for job in jobs:
    score, explain = calculate_rank(job, config)
    db.update_job_ranking(job['hash_key'], score, explain)
```

## Configuration

See `config/ranking.yml` for the ranking configuration format.

## Testing

```bash
# Run unit tests
pytest tests/unit/services/ranker/

# Run integration tests
pytest tests/integration/services/ranker/
```

## Future Enhancements (Phase 1)

- Advanced NLP for title keyword matching
- Geospatial distance calculations
- Fuzzy skill matching
- Machine learning-based scoring
- Time-decay factors for older postings

