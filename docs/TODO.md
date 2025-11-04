# Job-ETL — Phased TODO Checklist (from easy → hard)

> Work item = checkbox + short description.
> Each has **Acceptance Criteria (AC)**.
> Phases are ordered for typical delivery flow: scaffold → local MVP → quality/features → cloud.

---

## Phase 0 — Project Scaffold & Local Runtime (easiest)

* [x] **Initialize repo & project layout (monorepo)**

  * **AC:** `job-etl/` structure exists per spec (airflow/, dbt/, services/, config/, tests/, scripts/). `README.md` shows one-command run.

* [x] **Create `.env.example` and Docker secrets placeholders**

  * **AC:** `.env.example` includes non-sensitive vars; `secrets/` directory with README on mounting; secrets **not** tracked by git.

* [x] **Bootstrap Postgres locally**

  * **AC:** `docker-compose.yml` brings up Postgres with a named volume; `scripts/bootstrap_db.sql` runs automatically; schemas `raw`, `staging`, `marts` created.

* [x] **Bring up Airflow (LocalExecutor) via Docker Compose**

  * **AC:** Airflow web UI reachable; connection/variables bootstrap runs; example DAG shows in UI.

* [x] **dbt project skeleton**

  * **AC:** `dbt/job_dbt/` compiles; `profiles.yml.example` present; `dbt test` runs zero models (pending) without error.

* [x] **Write base models & seeds (enums, mappings)**

  * **AC:** `raw.job_postings_raw` + `staging.job_postings_stg` models compile; enum seeds load; generic tests defined but may be pending.

* [x] **CI: lint & unit test pipeline**

  * **AC:** GitHub Actions (or similar) runs `flake8/ruff + pytest + dbt compile`; fails on style/test errors.

---

## Phase 0.5 — First End-to-End Local MVP Path

* [x] **Source adapter interface (`SourceAdapter`) defined**

  * **AC:** Abstract class with `fetch()` & `map_to_common()`; contract tests with mocked payloads pass.

* [x] **Implement first provider in `source-extractor`**

  * **AC:** Can ingest ≥20 jobs on demand (adjusted for API limit); raw JSON stored to `raw.job_postings_raw` with `collected_at`, `source`.
  * **Implementation:** JSearch API (OpenWebNinja) adapter with retry logic, pagination, and comprehensive tests.

* [x] **Airflow DAG skeleton (`jobs_etl_daily`)**

  * **AC:** DAG contains tasks: `start → extract_{source} → normalize → enrich → dbt_models_core → dedupe_consolidate → rank → publish_hyper → notify_webhook_daily → end`; manual trigger succeeds for no-op steps.

* [x] **Normalizer service**

  * **AC:** Converts provider JSON to canonical rows; writes to `staging.job_postings_stg`; idempotent re-runs (no dup rows for same hash).

* [x] **Airflow integration: wire `source-extractor` into DAG**

  * **AC:** `extract_jsearch` calls source-extractor (PythonOperator/DockerOperator), uses Airflow Connection/Variables for creds, ingests to `raw.job_postings_raw`, returns extracted count via XCom.

* [x] **dbt core models (staging → marts)**

  * **AC:** Models for `int_*/marts` compile; `hash_key` derivation present; `unique`/`not_null` tests defined on `hash_key`.

* [x] **Deduplication logic (upsert)**

  * **AC:** `hash_key = md5(normalized company|title|location)`; re-runs update `last_seen_at`, preserve `first_seen_at`.
  * **Note:** Implemented in Python normalizer service

* [x] **Minimal ranker (stub scoring)**

  * **AC:** Writes `rank_score` (e.g., title/skill keyword hits only) and `rank_explain` JSON to `marts.fact_jobs`.
  * **Implementation:** Full ranker service with configurable weights, scoring algorithm, database operations, and Airflow integration. Includes tests and CI fixes.

* [ ] **Publisher: Tableau Hyper export**

  * **AC:** `.hyper` files produced under `./artifacts/`; opening in Tableau Desktop shows rows & essential fields.

* [ ] **Webhook notifier**

  * **AC:** After DAG success/fail, a POST hits configured webhook with counts & any failures (logged in Airflow).

* [ ] **MVP run schedule**

  * **AC:** DAG scheduled daily at **07:00 America/Toronto**; manual backfill possible from UI.

* [ ] **MVP tests pass**

  * **AC:** `pytest` unit/integration for services green; `dbt test` green on defined constraints.

---

## Phase 1 — Enrichment & Data Quality (feature depth)

* [ ] **Skills extraction (spaCy + keyword lists)**

  * **AC:** `enricher` populates `skills` (lowercased, distinct); unit tests cover extraction on sample postings.

* [ ] **Title standardization (taxonomy-driven)**

  * **AC:** `job_title_std` assigned via `config/taxonomy/titles.yml`; tests validate includes/excludes.

* [ ] **Location normalization**

  * **AC:** `location_std` filled; province/country inference; optional lat/lon via local lookup; null-safe behavior.

* [ ] **Salary normalization (→ CAD)**

  * **AC:** `salary_min_norm`, `salary_max_norm`, `salary_currency_norm='CAD'` computed using `fx_rates.yml`; tests for edge cases.

* [ ] **Company size normalization**

  * **AC:** Free-text mapped to bins (`51-200` etc.); unknown handled; acceptance values enforced in dbt.

* [ ] **Configurable ranking weights (`config/ranking.yml`)**

  * **AC:** Ranker reads weights & profile; recomputes `rank_score (0–100)`; `rank_explain` shows per-feature subscores.

* [ ] **DAG: add `dbt_tests` & idempotency tags**

  * **AC:** DAG fails fast on dbt test failure; retries on side-effect tasks with exponential backoff.

* [ ] **Great Expectations (critical suites)**

  * **AC:** Suites validate row counts, null thresholds, salary ranges; failures block downstream tasks.

* [ ] **Ad-hoc backfill DAG**

  * **AC:** A separate DAG runs a date-parametrized backfill; safe to re-run (no duplicates).

* [ ] **Tableau workbook: Ranked List + basic filters**

  * **AC:** Workbook page with filters (location, remote_type, salary range); top N list; fields clickable (Apply URL).

* [ ] **Publish to Tableau Server/Cloud (optional)**

  * **AC:** After local `.hyper` creation, publish to Tableau Server/Cloud using credentials; configurable via env/variables; errors logged and do not block local export.

---

## Phase 2 — AWS Lift (harder)

* [ ] **Build & push images to ECR**

  * **AC:** CI builds versioned images for all services; push to ECR with immutable tags.

* [ ] **Secrets in AWS Secrets Manager**

  * **AC:** No plaintext secrets in task defs; services load creds via IAM & env injection.

* [ ] **ECS Fargate deployment for microservices**

  * **AC:** Tasks for extractor/normalizer/enricher/ranker/publisher run on Fargate; health checks pass.

* [ ] **MWAA (or interim ECS Airflow) orchestration**

  * **AC:** DAG code lives in S3; MWAA schedules `jobs_etl_daily`; run success recorded in Airflow UI/CloudWatch.

* [ ] **S3 raw landing + RDS Postgres for staging/marts**

  * **AC:** Raw payloads in S3 with date partitioning; Postgres in RDS; network is private (security groups, subnets).

* [ ] **CloudWatch logs/metrics**

  * **AC:** Task & DAG logs visible in CloudWatch; essential metrics graphed (extracted/staged/enriched/ranked counts).

* [ ] **SQS decoupling (extractor → downstream)**

  * **AC:** Messages per posting (or batch) flow through SQS; downstream consumers scale horizontally; at-least-once processing with idempotency.

* [ ] **IAM least-privilege roles**

  * **AC:** Task roles limited to required services; KMS used for Secret decryption; security review checklist complete.

---

## Phase 3 — Observability, Reliability & Nice-to-Haves (hardest / optional)

* [ ] **Run stats mart & Tableau “Source Quality” page**

  * **AC:** `marts.run_stats` populated; dashboard shows extracted → deduped → matched counts over time.

* [ ] **Airflow SLAs + email on miss**

  * **AC:** Late/missed SLA triggers notification; incidents visible in Airflow UI & channel.

* [ ] **Replayability & blue/green config deploys**

  * **AC:** Changing YAML configs (taxonomy/ranking) can be toggled & rolled back without code rebuild.

* [ ] **Near-duplicate detection (Trigram/Levenshtein)**

  * **AC:** Similar postings grouped with thresholds; dedupe report shows merges vs retains.

* [ ] **Personal web UI (FastAPI) for browsing**

  * **AC:** Auth-less local UI lists ranked jobs, bookmarks; **not** part of MVP acceptance.

---

## Definition of Done per Phase

* **Phase 0.5 DoD (Local MVP):**

  * Daily DAG at 07:00 ET runs end-to-end locally.
  * ≥1 source integrated; ≥100 postings ingested.
  * Deduped unique rows in `marts.fact_jobs` on `hash_key`.
  * Minimal rank with `rank_explain`; Hyper export opens in Tableau.
  * Webhook summary posts after run.
  * `pytest` + `dbt test` pass.

* **Phase 1 DoD (Quality & Features):**

  * Enrichment (skills/title/location/salary/company size) active and tested.
  * Ranking is weight-driven; explainability persisted.
  * Great Expectations gates critical data; backfill DAG works.

* **Phase 2 DoD (AWS):**

  * Images in ECR; services on ECS Fargate; MWAA orchestrates.
  * Secrets in Secrets Manager; logs/metrics in CloudWatch.
  * Optional: S3 raw + RDS marts; SQS decoupling live.

---

## Cross-Cutting Acceptance Gates (apply throughout)

* **Idempotency:** Re-running a date/run_id does not duplicate or corrupt data.
* **Observability:** Each task emits clear logs; failures bubble to notifications.
* **Security:** No secrets in git; least-privilege IAM; pinned deps with audit.
* **Testing:** Unit + contract + integration + dbt tests green before merge.
* **Documentation:** `README` covers local run, env, secrets, and troubleshooting.

---

## Quickstart Order (single-day sprint suggestion)

1. Scaffold repo → 2) Postgres + Airflow up → 3) Source adapter (mock → real) → 4) Raw→staging dbt → 5) Dedupe + rank (stub) → 6) Hyper export → 7) Webhook → 8) Daily schedule.
