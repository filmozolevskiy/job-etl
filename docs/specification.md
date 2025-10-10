# Job-ETL: Incremental, Microservice-Based ETL for Job Postings (Learning Project)

> **Goal:** Build a hands-on ETL system—starting locally, then moving to AWS—that ingests job postings from 3rd-party APIs, cleans and normalizes them, enriches and ranks them against your profile, and publishes a **Tableau** dashboard and a **ranked list**. Everything is orchestrated by **Airflow**.

---

## 1) Objectives & Non-Goals

### Objectives

* Ingest job postings from one or more **3rd-party aggregation APIs** (e.g., RapidAPI providers).
* Clean, normalize, and **deduplicate** (unique by `company + title + location`).
* **Enrich** (skills NLP, title normalization, location standardization, salary currency normalization).
* **Rank** each posting using configurable weights: title keywords, skills, location, salary, employment type, seniority, remote/hybrid, company size.
* **Publish** to Tableau via **Hyper API** (dashboard + ranked list).
* **Orchestrate** with **Airflow** (daily 07:00 America/Toronto).
* Provide **visibility** (task logs + daily webhook digest).
* Ensure **durability** (tests) and **security** (secrets handling).

### Non-Goals (for MVP)

* No public web UI (Tableau is the visualization layer).
* No user auth/ACLs (single-user study project).
* No full SOC2/ISO hardening (basic security best practices only).
* No near-duplicate fuzzy matching in MVP (added later as enhancement).

---

## 2) Phased Delivery Plan (Incremental)

### Phase 0 — Local MVP (Docker Compose)

* **Core services**: `source-extractor`, `normalizer`, `enricher`, `ranker`, `publisher-hyper`.
* **Infra**: Postgres, Airflow (LocalExecutor), pgAdmin (optional).
* **Data model**: `raw` → `staging` (dbt) → `marts` (dbt).
* **Schedule**: daily 07:00 America/Toronto.
* **Notifications**: Slack/Discord webhook (counts, new matches, failures).
* **Observability**: Airflow logs + simple metrics counters.
* **Security**: `.env` + Docker secrets.
* **Testing**: pytest for services; dbt schema & generic tests.

### Phase 1 — Local+ (Quality & Features)

* Add **skills NLP** (spaCy/keyword rules), title taxonomy, location normalization, salary normalization.
* Add **configurable ranking weights** (YAML).
* Add **Great Expectations** suites (selected critical checks).
* Add **ad-hoc backfill** DAG and replayability (idempotent runs).

### Phase 2 — AWS Lift

* **Container registry**: ECR; **Compute**: ECS Fargate for microservices.
* **Orchestration**: Amazon **MWAA** (or self-managed on ECS/EKS as intermediate step).
* **Storage**: S3 raw landing; RDS Postgres for staging/marts (or keep Postgres locally in interim).
* **Secrets**: AWS Secrets Manager; **Logs/Metrics**: CloudWatch.
* **Queueing**: **SQS** between extractor and downstream processors (decoupling & scalability).

---

## 3) High-Level Architecture

### Microservices (separate containers)

1. **source-extractor**

   * Pulls from configured API providers (RapidAPI, etc.).
   * Writes JSON payloads to **raw schema** in Postgres (and/or S3 later).
2. **normalizer**

   * Converts provider-specific JSON → canonical rows (type mapping, enums).
3. **enricher**

   * Skills extraction (spaCy/rules), title standardization (taxonomy), location geo-norm, salary normalization (to a base currency).
4. **ranker**

   * Computes a **score** using configurable weights & profile preferences.
   * Persists ranked results to marts.
5. **publisher-hyper**

   * Builds `.hyper` files via **Tableau Hyper API** and (optionally) publishes to Tableau Server/Cloud or saves locally for Tableau Desktop.

> Airflow **DAG** orchestrates containerized tasks via DockerOperator (local) / ECSOperator (AWS).
> In AWS, optional **SQS** connects extractor → normalizer/enricher for parallel scaling.

---

## 4) Orchestration (Airflow)

**DAG: `jobs_etl_daily`** (07:00 America/Toronto)

1. `start` (Dummy)
2. `extract_{source}` (dynamic mapped tasks per source)
3. `load_raw_to_staging` (dbt run `stg_*`)
4. `normalize` (service call / container)
5. `enrich` (service call / container)
6. `dbt_models_core` (int_/dim_/fact_)
7. `dedupe_consolidate` (SQL/dbt incremental model)
8. `rank` (service call / container)
9. `dbt_tests` (schema+generic)
10. `publish_hyper` (publisher-hyper)
11. `notify_webhook_daily` (summary counts + failures)
12. `end` (Dummy)

**Reliability & Idempotency**

* Each run tagged with `run_id` (Airflow execution date).
* Inserts use **upserts** (ON CONFLICT) keyed by **hash_key** = `md5(lower(company)||'|'||lower(title)||'|'||lower(location))`.
* Side-effecting tasks are **retryable** (e.g., `retries=3`, exponential backoff).

---

## 5) Data Model (Postgres + dbt)

### Schemas

* `raw`: provider JSON + minimal parsed fields.
* `staging`: flattened provider-agnostic tables.
* `marts`: curated dims/facts (for Tableau).

### Core Tables

**`raw.job_postings_raw`**

| column       | type        | notes             |
| ------------ | ----------- | ----------------- |
| raw_id       | uuid pk     | generated         |
| source       | text        | API/provider name |
| payload      | jsonb       | original response |
| collected_at | timestamptz | ingestion time    |

**`staging.job_postings_stg`**

| column          | type        | notes                                                              |       |            |
| --------------- | ----------- | ------------------------------------------------------------------ | ----- | ---------- |
| provider_job_id | text        | if available                                                       |       |            |
| job_link        | text        | canonical URL                                                      |       |            |
| job_title       | text        | raw title                                                          |       |            |
| company         | text        | raw company name                                                   |       |            |
| company_size    | text        | enum from provider or mapped                                       |       |            |
| location        | text        | raw city/region/country                                            |       |            |
| remote_type     | text        | enum: `remote`, `hybrid`, `onsite`, `unknown`                      |       |            |
| contract_type   | text        | enum: `full_time`,`part_time`,`contract`,`intern`,`temp`,`unknown` |       |            |
| salary_min      | numeric     | nullable                                                           |       |            |
| salary_max      | numeric     | nullable                                                           |       |            |
| salary_currency | text        | ISO 4217                                                           |       |            |
| description     | text        | full text                                                          |       |            |
| skills_raw      | text[]      | parsed if provided                                                 |       |            |
| posted_at       | timestamptz | provider date                                                      |       |            |
| apply_url       | text        | canonical apply link                                               |       |            |
| source          | text        | provider                                                           |       |            |
| hash_key        | text pk     | `md5(company                                                       | title | location)` |
| first_seen_at   | timestamptz | min(collected_at)                                                  |       |            |
| last_seen_at    | timestamptz | max(collected_at)                                                  |       |            |

**`marts.dim_companies`**

| column            | type          | notes           |
| ----------------- | ------------- | --------------- |
| company_id        | surrogate key |                 |
| company           | text          | normalized      |
| company_size      | text          | normalized enum |
| source_first_seen | text          |                 |
| created_at        | timestamptz   |                 |

**`marts.fact_jobs`**

| column               | type          | notes                 |
| -------------------- | ------------- | --------------------- |
| job_id               | surrogate key |                       |
| hash_key             | text unique   | dedupe key            |
| job_title_std        | text          | standardized title    |
| company_id           | fk            |                       |
| location_std         | text          | standardized          |
| location_lat         | numeric       | optional              |
| location_lon         | numeric       | optional              |
| remote_type          | text          | enum                  |
| contract_type        | text          | enum                  |
| salary_min_norm      | numeric       | in base currency      |
| salary_max_norm      | numeric       | in base currency      |
| salary_currency_norm | text          | base (e.g., `CAD`)    |
| skills               | text[]        | extracted/normalized  |
| posted_at            | timestamptz   |                       |
| source               | text          |                       |
| apply_url            | text          |                       |
| rank_score           | numeric       | computed              |
| rank_explain         | jsonb         | feature contributions |
| ingested_at          | timestamptz   |                       |

> **dbt**: `stg_*` models handle type coercion, enum mapping, trimming, null normalization. `int_*` for enrichment joins. `marts` for final dims/facts. Include **tests**: `not_null`, `accepted_values`, `unique` on `hash_key`.

---

## 6) Deduplication & Idempotency

* **Primary rule**: uniqueness by `company + title + location` (case-folded, whitespace-collapsed).

  * `hash_key = md5(lower(normalize_ws(company)) || '|' || lower(normalize_ws(job_title)) || '|' || lower(normalize_ws(location)))`
* **Upsert** strategy:

  * If `hash_key` exists → update `last_seen_at`, merge freshest attributes (non-null preference).
  * If new → insert with `first_seen_at = now()`.
* **Later enhancement**: near-duplicate via fuzzy string similarity (e.g., Trigram) when adding more sources.

---

## 7) Enrichment

* **Skills extraction**: spaCy NER + curated keyword lists (tech stack, tools). Save in `skills` (distinct, lowercased).
* **Title standardization**: map raw titles to taxonomy (e.g., `Data Engineer`, `Analytics Engineer`, `Data Analyst`, etc.). YAML-driven rules (regex).
* **Location normalization**: parse city/region/country; optional geocoding (local lookup table); output `location_std`, lat/lon (optional).
* **Salary normalization**: convert to **CAD** using a configurable FX table (static YAML for MVP; pluggable later).
* **Company size normalization**: map free-text to bins: `1-10`, `11-50`, `51-200`, `201-500`, `501-1000`, `1001-5000`, `5001+`, `unknown`.

---

## 8) Ranking Engine

**Inputs (configurable weights in `config/ranking.yml`):**

```yaml
weights:
  title_keywords: 0.25
  skills_overlap: 0.30
  location_proximity: 0.10
  salary_band: 0.15
  employment_type: 0.05
  seniority_match: 0.07
  remote_type: 0.04
  company_size: 0.04

profile:
  title_keywords: ["data engineer", "analytics engineer", "etl", "airflow", "dbt"]
  must_have_skills: ["sql", "python"]
  nice_to_have_skills: ["airflow", "dbt", "aws", "docker", "kafka"]
  location_home: "Montreal, QC, CA"
  location_radius_km: 50
  salary_target_cad: {min: 70000, max: 120000}
  preferred_remote: ["remote", "hybrid"]
  preferred_contracts: ["full_time"]
  seniority: ["junior","intermediate"]
  preferred_company_sizes: ["51-200","201-500","501-1000"]
```

**Scoring (0–100):**

* `title_keywords`: normalized match score (regex/keyword hit ratio).
* `skills_overlap`: Jaccard / weighted overlap (`must_have` boost).
* `location_proximity`: 1.0 if within radius; partial if same province/country; else 0.
* `salary_band`: 1.0 if inside target; taper outside.
* `employment_type`: 1.0 if preferred; 0.5 if acceptable; else 0.
* `seniority_match`: based on title cues (e.g., “Senior”, “Lead”, “Manager”, “Junior”).
* `remote_type`: matches preferred list.
* `company_size`: preferred → 1.0; unknown → 0.5; otherwise 0.7.

`rank_score = 100 * Σ(weight_i * feature_score_i)`.
Store **`rank_explain`** as a JSON map of feature→subscore for transparency.

---

## 9) Tableau Output

* **Hyper tables**:

  * `fact_jobs` (ranked list)
  * `dim_companies`
* **Workbook (suggested pages)**:

  1. **Ranked List** (Top N, search by keyword, quick filters: location, remote_type, salary range).
  2. **Skills Coverage** (bar chart: how many top matches per skill).
  3. **Source Quality** (extracted vs deduped vs matched counts).
* **Fields shown**: title, company, location, rank_score, salary range, remote/hybrid, seniority cue, **Apply** URL (clickable).

---

## 10) Notifications (Webhook)

**Schedule:** After daily run.
**Payload (example):**

```json
{
  "run_id": "2025-10-09",
  "status": "success",
  "counts": {
    "extracted": 420,
    "staged": 410,
    "deduped_unique": 320,
    "enriched": 320,
    "ranked": 320,
    "top_matches": 25
  },
  "new_top_matches": [
    {"title":"Data Engineer","company":"Acme","location":"Montreal, QC","score":92,"apply_url":"..."},
    {"title":"Analytics Engineer","company":"Globex","location":"Remote","score":90,"apply_url":"..."}
  ],
  "failures": [],
  "duration_sec": 184
}
```

* **Channels**: Slack/Discord/Teams webhook URL from env/secret.
* **Failure mode**: if any task fails, send partial counts + failing task names.

---

## 11) Local Developer Environment

### Repo Layout (monorepo)

```
job-etl/
  README.md
  docker-compose.yml
  airflow/
    dags/jobs_etl_daily.py
    requirements.txt
  dbt/
    job_dbt/
      models/{raw,staging,int,marts}
      macros/
      seeds/
      profiles.yml.example
      dbt_project.yml
  services/
    source-extractor/
    normalizer/
    enricher/
    ranker/
    publisher-hyper/
  config/
    sources.yml
    ranking.yml
    taxonomy/
      titles.yml
      skills_dictionary.yml
      location_map.csv
      fx_rates.yml
  tests/
    unit/
    integration/
  scripts/
    bootstrap_db.sql
```

### Docker Compose (high level)

* `postgres` (with volumes)
* `airflow-scheduler`, `airflow-webserver`, `airflow-init`
* `source-extractor`, `normalizer`, `enricher`, `ranker`, `publisher-hyper`
* Optional: `pgadmin` or `adminer`

### Environment & Secrets

* `.env` for non-sensitive config (ports, local toggles).
* Docker **secrets** for API keys & webhook URLs (`secrets/` mounted to containers).
* Airflow connections/variables created via `airflow-init` command.

---

## 12) Source Integration (API Abstraction)

**Interface (`SourceAdapter`)**

* `fetch(page_token: str | None) -> (list[JobPostingRaw], next_token: str | None)`
* `map_to_common(raw) -> dict` (fields for `staging.job_postings_stg`)
* **Retry** with exponential backoff; respect rate limits.

**Add a new API**

1. Implement adapter in `services/source-extractor/adapters/{provider}.py`
2. Add provider config to `config/sources.yml`
3. Register provider in Airflow DAG (dynamic task mapping)
4. Update dbt seeds for enum mappings if needed

---

## 13) Security

* **Local**: `.env` + Docker secrets; avoid committing secrets.
* **Dependencies**: pin versions; run `pip-audit`/`safety` in CI.
* **Data**: no PII; encrypt secrets at rest (Docker secrets) and in AWS (KMS via Secrets Manager).
* **AWS**: least-privilege IAM; private subnets for RDS; security groups limit ingress; task roles per service.

---

## 14) Testing Strategy

* **Unit (pytest)**: parsing, normalization, enrichment, ranking.
* **Contract tests**: mock API responses per source adapter.
* **Integration**: service→DB flows in docker-compose; Airflow DAG dry runs.
* **dbt tests**:

  * `unique` & `not_null` on `hash_key`
  * `accepted_values` on enums
  * Referential integrity `fact_jobs.company_id → dim_companies.company_id`
* **Data Quality (later)**: Great Expectations suites for row counts, null thresholds, salary ranges.

---

## 15) Observability

* **MVP**: Airflow task logs; lightweight counters written to `marts.run_stats` for dashboarding.
* **Later**: CloudWatch (logs/metrics). S3 task logs w/ MWAA. Add Airflow SLAs & email on miss.

---

## 16) CI/CD (Local → AWS)

* **Git**: feature branches, PR checks.
* **CI**:

  * Lint & test (pytest + dbt compile/test).
  * Build images for services (Docker).
* **CD (later)**:

  * Push images to **ECR**.
  * Deploy ECS task definitions (Fargate).
  * MWAA DAG sync (S3 bucket).
  * Migrations via Alembic/dbt.

---

## 17) Risk & Mitigations

* **API schema changes** → isolate via adapters + jsonb raw store.
* **Rate limits** → backoff + scheduling windows; SQS decoupling in AWS.
* **Incomplete salary/location** → robust null handling; ranking falls back gracefully.
* **Small volumes** → design supports scale; enable parallelism when adding sources.

---

## 18) Acceptance Criteria

**MVP (Phase 0)**

* ✅ Airflow DAG runs at 07:00 ET and on-demand.
* ✅ At least one provider integrated; ≥100 postings ingested.
* ✅ Deduped unique rows in `marts.fact_jobs` keyed by `hash_key`.
* ✅ Rank scores computed and persisted with `rank_explain`.
* ✅ `.hyper` exported; Tableau dashboard shows ranked list with working filters.
* ✅ Webhook sends daily summary with counts and failures.
* ✅ pytest + dbt tests pass locally.

**Phase 1**

* ✅ Enrichment features active (skills, title, location, salary normalization).
* ✅ Configurable ranking weights via YAML; explainability present.
* ✅ Great Expectations checks for critical datasets.

**Phase 2**

* ✅ Containers in ECR; services on ECS Fargate.
* ✅ Airflow on MWAA schedules the pipeline.
* ✅ Secrets in AWS Secrets Manager; logs/metrics in CloudWatch.
* ✅ Optional S3 raw landing + RDS Postgres marts.

---

## 19) Example Task/Service Contracts

**`ranker` input (SQL view or table):**

* fields: `hash_key, job_title_std, skills[], location_std, salary_min_norm, salary_max_norm, remote_type, contract_type, company_size, posted_at`

**`ranker` output:**

* updates `marts.fact_jobs.rank_score` and `rank_explain` (JSON)

**Webhook**: POST to `$WEBHOOK_URL` with run summary JSON (see above).

---

## 20) Configuration Files (samples)

**`config/sources.yml`**

```yaml
providers:
  sample_api:
    base_url: https://example-rapidapi.com/jobs
    headers:
      X-RapidAPI-Key: ${RAPIDAPI_KEY}
    params:
      q: "data engineer"
      per_page: 100
    pagination:
      type: "cursor"
      cursor_param: "next"
```

**`config/taxonomy/titles.yml`**

```yaml
standard_titles:
  data engineer:
    includes: ["data engineer", "etl engineer", "pipeline engineer", "analytics engineer"]
    excludes: ["manager", "director", "qa"]
```

---

## 21) Local Runbook

1. `cp dbt/job_dbt/profiles.yml.example ~/.dbt/profiles.yml` and fill Postgres creds.
2. `cp .env.example .env` and set env vars (DB URL, webhook URL).
3. `docker compose up --build`
4. Open Airflow UI → trigger `jobs_etl_daily`.
5. After success, find exported `.hyper` in `./artifacts/` and open in Tableau Desktop (or configure Tableau Server publish).

---

## 22) Future Enhancements (Optional)

* Near-duplicate detection (Trigram/Levenshtein on title/company).
* Advanced NLP (embedding similarity for skills/title).
* Geospatial distance scoring using lat/lon.
* Salary inference from description patterns.
* Personal web UI (FastAPI) for browsing & bookmarking jobs.
* Data catalog (OpenMetadata) for lineage/quality tracking.

---
