# Job-ETL C4 Architecture Diagrams

This document contains C4 model diagrams for the Job-ETL system at multiple abstraction levels using **Mermaid**.

> **Note:** These diagrams render natively in GitHub, VS Code (with Markdown Preview), GitLab, and many other tools without plugins!

---

## ETL Pipeline Flow Diagram

For a detailed interactive flowchart of the daily ETL pipeline, see:

**[📊 View/Edit ETL Flow Diagram](job-etl-flow.drawio)**

This diagram shows:
- Complete Airflow DAG task flow (`jobs_etl_daily`)
- All microservices and their connections
- Database schemas (raw → staging → marts)
- External systems (JSearch API, SMTP, Tableau)
- Data flow arrows and service call relationships

**How to use:**
- **View on GitHub**: Click the link above (GitHub will show the XML, but you can download it)
- **Edit in Draw.io**: 
  1. Go to https://app.diagrams.net/
  2. File → Open from → Device
  3. Select `docs/architecture/job-etl-flow.drawio`
  4. Make your edits
  5. File → Save As → Save to your device
  6. Commit the updated file to git
- **Direct GitHub integration**: Use this URL format (replace `YOUR_USERNAME` with your GitHub username):
  ```
  https://app.diagrams.net/?mode=github#YOUR_USERNAME/job-etl/main/docs/architecture/job-etl-flow.drawio
  ```

---

## Level 1: System Context Diagram

Shows the Job-ETL system and its external dependencies from a high-level perspective.

```mermaid
C4Context
    title System Context Diagram for Job-ETL

    Person(user, "Data Analyst/Job Seeker", "Views job postings and analytics")

    System(job_etl, "Job-ETL System", "Extracts, transforms, enriches, and ranks job postings from multiple sources")

    System_Ext(rapidapi, "RapidAPI Job Providers", "Third-party job posting aggregation APIs")
    System_Ext(other_apis, "Other Job APIs", "Additional job posting sources")
    System_Ext(tableau_desktop, "Tableau Desktop", "Visualizes ranked job postings")
    System_Ext(webhook_services, "Webhook Services", "Slack/Discord for notifications")

    Rel(user, job_etl, "Configures ranking preferences, triggers manual runs", "Airflow UI")
    Rel(user, tableau_desktop, "Views dashboards and ranked lists", "Tableau Desktop")

    Rel(job_etl, rapidapi, "Fetches job postings", "HTTPS/REST")
    Rel(job_etl, other_apis, "Fetches job postings", "HTTPS/REST")
    Rel(job_etl, tableau_desktop, "Exports Hyper files", "File System")
    Rel(job_etl, webhook_services, "Sends daily summaries", "HTTPS/Webhooks")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Level 2: Container Diagram

Shows the internal architecture of the Job-ETL system with all containers (services, databases, applications).

```mermaid
C4Container
    title Container Diagram for Job-ETL System

    Person(user, "Data Analyst", "Manages and views job data")

    Container_Boundary(job_etl, "Job-ETL System") {
        Container(airflow_web, "Airflow Webserver", "Python/Flask", "Provides orchestration UI and API")
        Container(airflow_scheduler, "Airflow Scheduler", "Python", "Schedules and triggers DAG runs")
        
        Container(source_extractor, "Source Extractor", "Python/FastAPI", "Fetches raw job postings from external APIs")
        Container(normalizer, "Normalizer", "Python", "Transforms provider-specific data to canonical format")
        Container(enricher, "Enricher", "Python/spaCy", "Extracts skills, normalizes titles, locations, salaries")
        Container(ranker, "Ranker", "Python", "Scores jobs based on configurable weights")
        Container(publisher_hyper, "Publisher", "Python/Tableau Hyper API", "Generates Hyper files for Tableau")
        
        Container(dbt, "dbt Transformations", "dbt-core", "SQL transformations: staging → marts")
        
        ContainerDb(postgres, "PostgreSQL Database", "PostgreSQL 15", "Stores raw, staging, and marts data")
        ContainerDb(airflow_postgres, "Airflow Metadata DB", "PostgreSQL 15", "Stores Airflow metadata")
        ContainerDb(redis, "Redis Cache", "Redis 7", "Caches Airflow state")
        
        Container(config, "Configuration Files", "YAML", "sources.yml, ranking.yml, taxonomy files")
    }

    System_Ext(external_apis, "Job APIs", "RapidAPI and other providers")
    System_Ext(tableau, "Tableau Desktop", "Visualization tool")
    System_Ext(webhooks, "Webhook Services", "Slack/Discord")

    Rel(user, airflow_web, "Manages DAGs, views logs", "HTTPS:8080")
    Rel(user, tableau, "Views dashboards", "Hyper files")

    Rel(airflow_web, airflow_postgres, "Reads/writes metadata", "PostgreSQL")
    Rel(airflow_scheduler, airflow_postgres, "Reads/writes metadata", "PostgreSQL")
    Rel(airflow_scheduler, redis, "Caches state", "Redis Protocol")

    Rel(airflow_scheduler, source_extractor, "Triggers extraction", "Docker exec")
    Rel(airflow_scheduler, normalizer, "Triggers normalization", "Docker exec")
    Rel(airflow_scheduler, enricher, "Triggers enrichment", "Docker exec")
    Rel(airflow_scheduler, ranker, "Triggers ranking", "Docker exec")
    Rel(airflow_scheduler, publisher_hyper, "Triggers publishing", "Docker exec")
    Rel(airflow_scheduler, dbt, "Runs transformations", "CLI")

    Rel(source_extractor, external_apis, "Fetches job postings", "HTTPS/REST")
    Rel(source_extractor, postgres, "Writes raw JSON", "PostgreSQL:5432")
    Rel(source_extractor, config, "Reads source configs", "File System")

    Rel(dbt, postgres, "Transforms: raw → staging", "PostgreSQL:5432")
    Rel(normalizer, postgres, "Reads staging, writes normalized", "PostgreSQL:5432")
    Rel(enricher, postgres, "Reads/writes enriched data", "PostgreSQL:5432")
    Rel(enricher, config, "Reads taxonomy configs", "File System")
    Rel(ranker, postgres, "Reads enriched, writes scores", "PostgreSQL:5432")
    Rel(ranker, config, "Reads ranking.yml", "File System")
    Rel(publisher_hyper, postgres, "Reads marts", "PostgreSQL:5432")
    Rel(publisher_hyper, tableau, "Exports Hyper files", "File System")
    Rel(airflow_scheduler, webhooks, "Sends notifications", "HTTPS")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Level 3: Component Diagram - Source Extractor

Details the internal components of the Source Extractor service.

```mermaid
C4Component
    title Component Diagram - Source Extractor Service

    Container_Boundary(source_extractor, "Source Extractor Service") {
        Component(main, "Main Orchestrator", "Python", "Coordinates extraction process")
        Component(adapter_factory, "Adapter Factory", "Python", "Creates appropriate source adapter")
        Component(rapidapi_adapter, "RapidAPI Adapter", "Python", "Implements SourceAdapter for RapidAPI")
        Component(generic_adapter, "Generic API Adapter", "Python", "Implements SourceAdapter for generic REST APIs")
        Component(retry_handler, "Retry Handler", "Python", "Exponential backoff and rate limiting")
        Component(mapper, "Data Mapper", "Python", "Maps provider schema to common format")
        Component(db_writer, "Database Writer", "Python/SQLAlchemy", "Writes to raw.job_postings_raw")
    }

    ContainerDb(postgres, "PostgreSQL Database", "PostgreSQL 15", "raw schema")
    ContainerDb(config, "sources.yml", "YAML", "Provider configurations")
    System_Ext(external_apis, "Job APIs", "External providers")

    Rel(main, adapter_factory, "Creates adapter")
    Rel(adapter_factory, rapidapi_adapter, "Instantiates")
    Rel(adapter_factory, generic_adapter, "Instantiates")
    Rel(adapter_factory, config, "Reads config")

    Rel(rapidapi_adapter, retry_handler, "Uses")
    Rel(generic_adapter, retry_handler, "Uses")
    Rel(retry_handler, external_apis, "Fetches with retries", "HTTPS/REST")

    Rel(rapidapi_adapter, mapper, "Maps response")
    Rel(generic_adapter, mapper, "Maps response")

    Rel(main, db_writer, "Persists data")
    Rel(db_writer, postgres, "Writes raw JSON", "PostgreSQL")

    UpdateLayoutConfig($c4ShapeInRow="2", $c4BoundaryInRow="1")
```

---

## Level 3: Component Diagram - Ranker Service

Details the internal components of the Ranker service.

```mermaid
C4Component
    title Component Diagram - Ranker Service

    Container_Boundary(ranker, "Ranker Service") {
        Component(main, "Main Orchestrator", "Python", "Coordinates ranking process")
        Component(config_loader, "Config Loader", "Python", "Loads ranking.yml with weights and profile")
        Component(db_reader, "Database Reader", "Python/SQLAlchemy", "Reads enriched job data")
        Component(scoring_engine, "Scoring Engine", "Python", "Calculates weighted scores")
        
        Component(title_scorer, "Title Keyword Scorer", "Python", "Scores title matches")
        Component(skills_scorer, "Skills Overlap Scorer", "Python", "Calculates Jaccard similarity")
        Component(location_scorer, "Location Proximity Scorer", "Python", "Scores location fit")
        Component(salary_scorer, "Salary Band Scorer", "Python", "Scores salary alignment")
        Component(employment_scorer, "Employment Type Scorer", "Python", "Scores contract type")
        Component(seniority_scorer, "Seniority Match Scorer", "Python", "Scores seniority fit")
        Component(remote_scorer, "Remote Type Scorer", "Python", "Scores remote preference")
        Component(company_scorer, "Company Size Scorer", "Python", "Scores company size preference")
        
        Component(explainer, "Score Explainer", "Python", "Generates rank_explain JSON")
        Component(db_writer, "Database Writer", "Python/SQLAlchemy", "Updates rank_score and rank_explain")
    }

    ContainerDb(postgres, "PostgreSQL Database", "PostgreSQL 15", "marts schema")
    ContainerDb(ranking_config, "ranking.yml", "YAML", "Weights and profile")

    Rel(main, config_loader, "Loads config")
    Rel(config_loader, ranking_config, "Reads")
    Rel(main, db_reader, "Fetches jobs")
    Rel(db_reader, postgres, "Reads marts.fact_jobs", "PostgreSQL")
    Rel(main, scoring_engine, "Scores each job")
    Rel(scoring_engine, title_scorer, "Uses")
    Rel(scoring_engine, skills_scorer, "Uses")
    Rel(scoring_engine, location_scorer, "Uses")
    Rel(scoring_engine, salary_scorer, "Uses")
    Rel(scoring_engine, employment_scorer, "Uses")
    Rel(scoring_engine, seniority_scorer, "Uses")
    Rel(scoring_engine, remote_scorer, "Uses")
    Rel(scoring_engine, company_scorer, "Uses")
    Rel(scoring_engine, explainer, "Generates explanation")
    Rel(main, db_writer, "Persists scores")
    Rel(db_writer, postgres, "Updates rank_score, rank_explain", "PostgreSQL")

    UpdateLayoutConfig($c4ShapeInRow="3", $c4BoundaryInRow="1")
```

---

## Data Flow Diagram

Shows the data transformation pipeline from extraction to publication.

```mermaid
flowchart LR
    APIs[External APIs]
    Raw[(raw.job_postings_raw)]
    Staging[(staging.job_postings_stg)]
    DimCompanies[(marts.dim_companies)]
    FactJobs[(marts.fact_jobs)]
    Tableau[Tableau Desktop]

    APIs -->|"1. Extract<br/>(source-extractor)<br/>JSON payload"| Raw
    Raw -->|"2. Load to Staging<br/>(dbt stg_*)<br/>Type coercion, enums"| Staging
    Staging -->|"3. Normalize<br/>(normalizer)<br/>Deduplication by hash_key"| Staging
    Staging -->|"4. Enrich<br/>(enricher)<br/>Skills NLP, title/location/salary norm"| Staging
    Staging -->|"5. dbt Core Models<br/>(dbt int_*/dim_*)<br/>Dimensions"| DimCompanies
    Staging -->|"5. dbt Core Models<br/>(dbt fact_*)<br/>Facts"| FactJobs
    FactJobs -->|"6. Rank<br/>(ranker)<br/>Calculate rank_score"| FactJobs
    FactJobs -->|"7. Publish<br/>(publisher-hyper)<br/>.hyper files"| Tableau

    classDef database fill:#4DB8E8,stroke:#2980B9,color:#000
    classDef external fill:#999999,stroke:#666666,color:#fff
    
    class Raw,Staging,DimCompanies,FactJobs database
    class APIs,Tableau external
```

### Schema Details

**raw.job_postings_raw**
- `raw_id` (uuid pk)
- `source` (text)
- `payload` (jsonb)
- `collected_at` (timestamp)

**staging.job_postings_stg**
- `hash_key` (text pk) = md5(company|title|location)
- `job_title`, `company`, `location`
- `remote_type`, `contract_type`
- `salary_min/max`, `currency`
- `skills_raw` (text[])
- `first_seen_at`, `last_seen_at`

**marts.fact_jobs**
- `job_id` (surrogate key)
- `hash_key` (unique)
- `job_title_std`, `company_id` (fk)
- `location_std`, `lat/lon`
- `skills` (text[])
- `rank_score`, `rank_explain` (jsonb)

---

## Airflow DAG Diagram

Shows the task dependencies in the main Airflow DAG.

```mermaid
flowchart TD
    Start([start]):::dummy
    Extract1[extract_source_1]:::docker
    Extract2[extract_source_2]:::docker
    ExtractN[extract_source_n]:::docker
    LoadStaging[load_raw_to_staging<br/>dbt run --models stg_*]:::dbt
    Normalize[normalize]:::docker
    Enrich[enrich]:::docker
    DbtCore[dbt_models_core<br/>dbt run --models int_* dim_* fact_*]:::dbt
    Dedupe[dedupe_consolidate]:::dbt
    Rank[rank<br/>Calculate rank_score]:::docker
    DbtTests[dbt_tests<br/>dbt test]:::dbt
    Publish[publish_hyper<br/>Export .hyper files]:::docker
    Notify[notify_webhook_daily<br/>Send to Slack/Discord]:::webhook
    End([end]):::dummy

    Start --> Extract1
    Start --> Extract2
    Start --> ExtractN
    
    Extract1 --> LoadStaging
    Extract2 --> LoadStaging
    ExtractN --> LoadStaging
    
    LoadStaging --> Normalize
    Normalize --> Enrich
    Enrich --> DbtCore
    DbtCore --> Dedupe
    Dedupe --> Rank
    Rank --> DbtTests
    DbtTests --> Publish
    Publish --> Notify
    Notify --> End

    classDef docker fill:#AED6F1,stroke:#3498DB,stroke-width:2px,color:#000
    classDef dbt fill:#A9DFBF,stroke:#27AE60,stroke-width:2px,color:#000
    classDef webhook fill:#F9E79F,stroke:#F39C12,stroke-width:2px,color:#000
    classDef dummy fill:#D5D8DC,stroke:#95A5A6,stroke-width:2px,color:#000
```

**Schedule:** Daily at 07:00 America/Toronto

**Task Types:**
- 🔵 **Docker Service** - Containerized microservices
- 🟢 **dbt Task** - SQL transformations and tests
- 🟡 **Webhook** - Notification services
- ⚪ **Dummy Task** - Pipeline markers

**Notes:**
- `extract_source_*` are dynamically mapped from `sources.yml`
- Each task has `retries=3` with exponential backoff
- All operations are idempotent (safe to re-run)

---

## Deployment Diagram - Local (Docker Compose)

Shows the physical deployment architecture for local development.

```mermaid
flowchart TB
    subgraph DevMachine["💻 Developer Machine (Windows/Mac/Linux)"]
        subgraph Docker["🐳 Docker Engine"]
            subgraph Network["job-etl-network (Bridge Network)"]
                AirflowWeb["airflow-webserver<br/>:8080"]
                AirflowScheduler["airflow-scheduler"]
                Postgres["postgres<br/>PostgreSQL 15<br/>:5432"]
                AirflowPostgres["airflow-postgres<br/>PostgreSQL 15"]
                Redis["redis<br/>Redis 7<br/>:6379"]
                PgAdmin["pgadmin (optional)<br/>:8081"]
            end
        end
        
        subgraph FileSystem["📁 File System"]
            Volumes["Docker Volumes<br/>• postgres_data<br/>• airflow_postgres_data<br/>• redis_data"]
            Mounts["Bind Mounts<br/>• ./dbt<br/>• ./config<br/>• ./secrets<br/>• ./artifacts"]
        end
    end
    
    Browser["🌐 Web Browser<br/>localhost:8080, 8081"]
    Tableau["📊 Tableau Desktop<br/>Reads .hyper files"]
    
    Browser -.->|"Access UI"| AirflowWeb
    Browser -.->|"Database Admin"| PgAdmin
    AirflowWeb -->|"Metadata"| AirflowPostgres
    AirflowScheduler -->|"Metadata"| AirflowPostgres
    AirflowScheduler -->|"Cache"| Redis
    AirflowScheduler -->|"Data Operations"| Postgres
    PgAdmin -.->|"Manage DB"| Postgres
    Tableau -.->|"Read Files"| Mounts
    
    Postgres -.->|"Persist"| Volumes
    AirflowPostgres -.->|"Persist"| Volumes
    Redis -.->|"Persist"| Volumes

    classDef container fill:#AED6F1,stroke:#3498DB,stroke-width:2px
    classDef database fill:#F8C471,stroke:#F39C12,stroke-width:2px
    classDef storage fill:#D7BDE2,stroke:#8E44AD,stroke-width:2px
    classDef external fill:#A9DFBF,stroke:#27AE60,stroke-width:2px
    
    class AirflowWeb,AirflowScheduler,PgAdmin container
    class Postgres,AirflowPostgres,Redis database
    class Volumes,Mounts storage
    class Browser,Tableau external
```

**Key Components:**
- **Containers:** Run microservices and Airflow components
- **Databases:** PostgreSQL for data + metadata, Redis for caching
- **Volumes:** Persistent storage for database data
- **Bind Mounts:** Live sync of code, config, secrets, and artifacts

**Ports:**
- `8080` - Airflow UI
- `8081` - pgAdmin (optional)
- `5432` - PostgreSQL
- `6379` - Redis

---

## Deployment Diagram - AWS (Phase 2)

Shows the planned AWS architecture for production deployment.

```mermaid
flowchart TB
    subgraph AWS["☁️ AWS Cloud (us-east-1)"]
        subgraph VPC["VPC (Private/Public Subnets)"]
            MWAA["Amazon MWAA<br/>(Managed Airflow)"]
            
            subgraph ECS["ECS Fargate Cluster<br/>(Serverless Compute)"]
                Extractor["source-extractor<br/>ECS Task"]
                Normalizer["normalizer<br/>ECS Task"]
                Enricher["enricher<br/>ECS Task"]
                Ranker["ranker<br/>ECS Task"]
                Publisher["publisher-hyper<br/>ECS Task"]
            end
            
            RDS[("Amazon RDS<br/>PostgreSQL 15<br/>(Multi-AZ)")]
            SQS["Amazon SQS<br/>job-queue<br/>(Decoupling)"]
        end
        
        subgraph S3["Amazon S3<br/>(Object Storage)"]
            RawBucket["raw-landing-bucket"]
            HyperBucket["hyper-exports-bucket"]
            DagBucket["mwaa-dags-bucket"]
        end
        
        ECR["Amazon ECR<br/>(Container Registry)<br/>Service Images"]
        
        SecretsManager["AWS Secrets Manager<br/>(KMS Encrypted)<br/>API Keys, DB Passwords"]
        
        subgraph CloudWatch["Amazon CloudWatch"]
            Logs["CloudWatch Logs"]
            Metrics["CloudWatch Metrics"]
        end
    end
    
    ExternalAPIs["External Job APIs<br/>(RapidAPI, etc.)"]
    TableauServer["Tableau Server/Cloud<br/>(Dashboard Hosting)"]
    
    MWAA -->|"Trigger tasks<br/>(ECSOperator)"| ECS
    MWAA -->|"Read DAGs"| DagBucket
    MWAA -->|"Read secrets"| SecretsManager
    
    Extractor -->|"Fetch jobs"| ExternalAPIs
    Extractor -->|"Write raw JSON"| RawBucket
    Extractor -->|"Send messages"| SQS
    
    SQS -->|"Receive messages"| Normalizer
    Normalizer -->|"Write/read data"| RDS
    Enricher -->|"Enrich data"| RDS
    Ranker -->|"Score jobs"| RDS
    
    Publisher -->|"Read marts"| RDS
    Publisher -->|"Export .hyper"| HyperBucket
    Publisher -.->|"Publish (optional)"| TableauServer
    
    ECS -->|"Pull images"| ECR
    ECS -->|"Send logs/metrics"| CloudWatch
    MWAA -->|"Send logs/metrics"| CloudWatch

    classDef aws fill:#FF9900,stroke:#CC7A00,stroke-width:3px,color:#fff
    classDef compute fill:#F58536,stroke:#C66B2B,stroke-width:2px,color:#000
    classDef storage fill:#569A31,stroke:#447A27,stroke-width:2px,color:#fff
    classDef database fill:#3B48CC,stroke:#2E3A9F,stroke-width:2px,color:#fff
    classDef security fill:#DD344C,stroke:#B02A3D,stroke-width:2px,color:#fff
    classDef monitoring fill:#759C3E,stroke:#5D7D32,stroke-width:2px,color:#fff
    classDef external fill:#666,stroke:#333,stroke-width:2px,color:#fff
    
    class MWAA,ECS,Extractor,Normalizer,Enricher,Ranker,Publisher compute
    class S3,RawBucket,HyperBucket,DagBucket,ECR storage
    class RDS,SQS database
    class SecretsManager security
    class CloudWatch,Logs,Metrics monitoring
    class ExternalAPIs,TableauServer external
```

**AWS Services:**
- 🟠 **MWAA** - Managed Airflow for orchestration
- 🟠 **ECS Fargate** - Serverless container compute
- 🟢 **S3** - Object storage for raw data, DAGs, and exports
- 🔵 **RDS PostgreSQL** - Managed database (Multi-AZ)
- 🔵 **SQS** - Message queue for decoupling services
- 🔴 **Secrets Manager** - KMS-encrypted secrets with rotation
- 🟡 **CloudWatch** - Centralized logs and metrics
- 🟢 **ECR** - Private container registry

**Benefits:**
- ✅ Fully managed services (less operational overhead)
- ✅ Auto-scaling with Fargate
- ✅ High availability (Multi-AZ RDS)
- ✅ Decoupled architecture with SQS
- ✅ Secure secrets management with KMS encryption

---

## Database Schema Diagram

Shows the relationships between database tables across schemas.

```mermaid
erDiagram
    job_postings_raw ||--o{ job_postings_stg : "dbt stg_* transform"
    job_postings_stg ||--o{ dim_companies : "dbt dim_* denormalize"
    job_postings_stg ||--o{ fact_jobs : "dbt fact_* enrich & rank"
    dim_companies ||--o{ fact_jobs : "company_id FK"

    job_postings_raw {
        uuid raw_id PK
        text source
        jsonb payload
        timestamptz collected_at
    }

    job_postings_stg {
        text hash_key PK "md5(company|title|location)"
        text provider_job_id
        text job_link
        text job_title
        text company
        text company_size
        text location
        text remote_type
        text contract_type
        numeric salary_min
        numeric salary_max
        text salary_currency
        text description
        text[] skills_raw
        timestamptz posted_at
        text apply_url
        text source
        timestamptz first_seen_at
        timestamptz last_seen_at
    }

    dim_companies {
        serial company_id PK
        text company
        text company_size
        text source_first_seen
        timestamptz created_at
    }

    fact_jobs {
        serial job_id PK
        text hash_key UK "unique"
        text job_title_std
        int company_id FK
        text location_std
        numeric location_lat
        numeric location_lon
        text remote_type
        text contract_type
        numeric salary_min_norm
        numeric salary_max_norm
        text salary_currency_norm
        text[] skills
        timestamptz posted_at
        text source
        text apply_url
        numeric rank_score
        jsonb rank_explain "feature contributions"
        timestamptz ingested_at
    }

    run_stats {
        text run_id PK
        timestamptz execution_date
        int extracted_count
        int staged_count
        int deduped_count
        int enriched_count
        int ranked_count
        int duration_sec
        text status
    }
```

### Schema Organization

**📦 raw** - Provider JSON + minimal parsing
- Preserves original API responses
- JSONB for flexibility

**📦 staging** - Flattened provider-agnostic tables
- Canonical format across all sources
- Deduplication via `hash_key`
- Tracks `first_seen_at` and `last_seen_at`

**📦 marts** - Curated dimensions and facts for Tableau
- Star schema design
- Normalized dimensions (`dim_companies`)
- Enriched facts with scores (`fact_jobs`)
- Explainable AI with `rank_explain` JSON

### Key Concepts

**Deduplication Key:**
```sql
hash_key = md5(
  lower(normalize_ws(company)) || '|' ||
  lower(normalize_ws(job_title)) || '|' ||
  lower(normalize_ws(location))
)
```

**Rank Explainability:**
```json
{
  "title_keywords": 0.95,
  "skills_overlap": 0.80,
  "location_proximity": 1.0,
  "salary_band": 0.75,
  "employment_type": 1.0,
  "seniority_match": 0.85,
  "remote_type": 1.0,
  "company_size": 0.70
}
```

---

## How to View These Diagrams

### ✅ Option 1: GitHub/GitLab (Recommended)
**No installation required!** These Mermaid diagrams render automatically when you view this file on:
- GitHub
- GitLab
- Azure DevOps
- Bitbucket

Just open the file in your browser and scroll through!

### ✅ Option 2: VS Code (Built-in)
1. Open this file in VS Code
2. Click the **"Open Preview"** button (top-right corner)
3. Or press: `Ctrl+Shift+V` (Windows/Linux) or `Cmd+Shift+V` (Mac)
4. Diagrams render automatically! ✨

**No extensions needed!** VS Code has native Mermaid support in Markdown preview.

### ✅ Option 3: Enhanced VS Code Preview
For better rendering with pan/zoom:

1. Install extension: **"Markdown Preview Mermaid Support"** by Matt Bierner
2. Open this file
3. Use preview as above
4. Get interactive diagrams with better styling

### ✅ Option 4: Mermaid Live Editor
1. Visit: https://mermaid.live/
2. Copy any diagram code block
3. Paste in the editor
4. View, edit, and export (PNG, SVG, PDF)

### ✅ Option 5: IntelliJ/PyCharm
1. Install plugin: **"Mermaid"**
2. Open this file
3. Preview pane shows diagrams automatically

### ✅ Option 6: Command Line (Export to Images)
```bash
# Install Mermaid CLI
npm install -g @mermaid-js/mermaid-cli

# Export all diagrams to PNG
mmdc -i docs/architecture/c4-diagrams.md -o docs/architecture/diagrams/

# Export to SVG (better quality)
mmdc -i docs/architecture/c4-diagrams.md -o docs/architecture/diagrams/ -t svg

# Export single diagram
mmdc -i diagram.mmd -o diagram.png
```

---

## Diagram Maintenance

When updating the architecture:
1. Update `specification.md` first
2. Update corresponding C4 diagram(s)
3. Keep all levels synchronized
4. Regenerate images if using static exports
5. Test rendering in GitHub preview

---

## Quick Start

**Viewing diagrams right now:**
1. If you're on GitHub/GitLab: You're already seeing them! 🎉
2. If you're in VS Code: Press `Ctrl+Shift+V` (or `Cmd+Shift+V`)
3. If neither: Copy a diagram to https://mermaid.live/

---

## Additional Resources

- [C4 Model Documentation](https://c4model.com/)
- [Mermaid Documentation](https://mermaid.js.org/)
- [Mermaid Live Editor](https://mermaid.live/)
- [Job-ETL Specification](../specification.md)
- [Job-ETL TODO](../TODO.md)

---

## Why Mermaid?

✅ **Native GitHub/GitLab support** - No plugins needed  
✅ **Built into VS Code** - Instant preview  
✅ **Text-based** - Easy to version control  
✅ **Simple syntax** - Faster to write and maintain  
✅ **Wide tool support** - Works everywhere  
✅ **Export options** - Can generate PNG/SVG/PDF when needed

