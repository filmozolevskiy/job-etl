# publisher_hyper

Exports marts tables (`marts.fact_jobs`, `marts.dim_companies`) to a Tableau `.hyper` file under `./artifacts/`.

## Usage

```bash
export DATABASE_URL=postgresql://user:password@host:5432/job_etl
python -m services.publisher_hyper.main --output-dir artifacts --filename jobs_ranked.hyper
```

## Dependencies
- `psycopg2-binary`
- `tableauhyperapi` (lazy-imported at runtime)

Note: CI does not install `tableauhyperapi` by default; the module is imported lazily to avoid breaking tests.

