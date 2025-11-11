Here is the combined Markdown documentation file for the two endpoints of the JSearch API (by OpenWeb Ninja): Job Search and Job Details.

# JSearch API Documentation  
Real-time job listings and job detail retrieval from OpenWeb Ninja.  
(Endpoints: Job Search + Job Details)  
Refer to the provider site for latest changes. :contentReference[oaicite:2]{index=2}  

---

## Authentication  
For all endpoints:  
- The provider documentation specifies `Authorization: Bearer <YOUR_API_KEY>`, however the live API currently requires `X-API-Key: <YOUR_API_KEY>`.  
- Ensure your API key is valid and you are within rate limits. :contentReference[oaicite:3]{index=3}  

---

## Base URL  
> `https://api.openwebninja.com/v1` (or as specified in your plan/documentation)  
> Example: `https://api.openwebninja.com/v1/job-search` :contentReference[oaicite:4]{index=4}  

---

### 1. Job Search Endpoint  
**GET** `/job-search`  
> Retrieves a list of job postings matching search criteria.

#### Request Parameters

| Parameter            | Type     | Required | Description |
|----------------------|----------|----------|-------------|
| `query`              | string   | ✅       | Search query text (e.g., "software engineer New York") :contentReference[oaicite:5]{index=5} |
| `country`            | string   | ❌       | ISO 3166-1 alpha-2 country code from which to return postings (e.g., `ca`, `us`, `de`). Required for country-specific searches. |
| `page`               | integer  | ❌       | Page number of results (pagination) |
| `num_pages`          | integer  | ❌       | Number of pages to fetch (limit) :contentReference[oaicite:6]{index=6} |
| `date_posted`        | string   | ❌       | Filter by when job was posted (e.g., “today”, “3days”, “week”, “month”, “all”) :contentReference[oaicite:7]{index=7} |
| `remote_jobs_only`   | boolean  | ❌       | Only remote jobs (`true`/`false`) :contentReference[oaicite:8]{index=8} |
| `employment_types`   | string[] | ❌       | Comma-separated list, e.g., “FULLTIME,CONTRACTOR,PARTTIME” :contentReference[oaicite:9]{index=9} |
| `job_requirements`   | string[] | ❌       | Comma-separated list of filters like “no_experience”, “more_than_3_years_experience”, “no_degree” :contentReference[oaicite:10]{index=10} |
| `radius`             | integer  | ❌       | Search radius in km from the given location (for geo filtering) :contentReference[oaicite:11]{index=11} |

> **Note:** To retrieve postings for a specific country you must include the `country` parameter. For example, `country=de` is required when querying for jobs in Germany. Supported values follow the [ISO&nbsp;3166-1 alpha-2](https://en.wikipedia.org/wiki/ISO_3166-1_alpha-2) list.
>
> **Implementation note:** The live API currently exposes the legacy path `/jsearch/search` with the `X-API-Key` header. Requests to `/v1/job-search` still return `403 Missing Authentication Token`.

#### Sample Request  
```http
GET https://api.openwebninja.com/v1/job-search?query=Node.js+Developer+New+York&page=1
Authorization: Bearer YOUR_API_KEY

Sample Response
{
  "status": "OK",
  "request_id": "8739be65-eeab-43b6-859b-ccc6ec8b77e1",
  "parameters": {
    "query": "web developer in texas usa",
    "page": 1,
    "num_pages": 1
  },
  "data": [
    {
      "job_id": "JviQ_0mnlXoAAAAAAAAAAA==",
      "employer_name": "Archetype Permanent Solutions",
      "employer_logo": null,
      "employer_website": null,
      "job_publisher": "Talent.com",
      "job_employment_type": "FULLTIME",
      "job_title": "Web developer",
      "job_apply_link": "https://www.talent.com/view?id=d9389c3c7cd3",
      "job_apply_is_direct": false,
      "job_apply_quality_score": 0.4979,
      "job_description": "Responsibilities :\n• Develop and maintain web applications …\n",
      "job_is_remote": false,
      "job_posted_at_timestamp": 1685577600,
      "job_posted_at_datetime_utc": "2023-06-01T00:00:00.000Z",
      "job_city": "Austin",
      "job_state": "TX",
      "job_country": "US",
      "job_latitude": 30.267153,
      "job_longitude": -97.74306,
      "job_benefits": null,
      "job_job_title": null,
      "job_posting_language": "en",
      "job_onet_soc": "15113400",
      "job_onet_job_zone": "3",
      "job_occupational_categories": ["15-1254.00"]
    }
  ]
}

### 2. Job Details Endpoint
GET https://api.openwebninja.com/v1/job-details?job_id=t-AKAI-wU29Jup6MAAAAAA==
Authorization: Bearer YOUR_API_KEY

Sample Response
{
  "job_id": "t-AKAI-wU29Jup6MAAAAAA==",
  "employer_name": "Intetics",
  "employer_logo": "https://encrypted-tbn0.gstatic.com/images?q=tbn:ANd9GcTK_KU_MWJwgob7h3oWQdO6HZgRFDKAYKbnACq0&s=0",
  "employer_website": "http://intetics.com",
  "employer_company_type": "Computer Services",
  "employer_linkedin": null,
  "job_publisher": "LinkedIn",
  "job_employment_type": "FULLTIME",
  "job_title": "Senior Node.js Developer",
  "job_apply_link": "https://www.linkedin.com/jobs/view/senior-node-js-developer-at-intetics-…",
  "job_apply_is_direct": false,
  "job_apply_quality_score": 0.7454,
  "apply_options": [
    {
      "publisher": "LinkedIn",
      "apply_link": "https://www.linkedin.com/jobs/view/senior-node-js-developer-at-intetics-3967661687?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
      "is_direct": false
    },
    {
      "publisher": "Monster",
      "apply_link": "https://www.monster.com/job-openings/senior-node-js-developer-new-york-ny-…?utm_campaign=google_jobs_apply&utm_source=google_jobs_apply&utm_medium=organic",
      "is_direct": true
    }
  ],
  "job_description": "Intetics Inc., a leading global technology company providing custom software application …",
  "job_is_remote": false,
  "job_posted_at_timestamp": 1720182992,
  "job_posted_at_datetime_utc": "2024-07-05T12:36:32.000Z",
  "job_city": "New York",
  "job_state": "NY",
  "job_country": "US",
  "job_latitude": 40.712776,
  "job_longitude": -74.005974,
  "job_benefits": null,
  "job_google_link": "https://www.google.com/search?gl=us&hl=en&rciv=jb&q=node.js+developer+in+new-york,usa&…",
  "job_offer_expiration_datetime_utc": "2025-01-01T12:47:25.000Z",
  "job_offer_expiration_timestamp": 1735735645,
  "job_required_experience": {
    "no_experience_required": "false",
    "required_experience_in_months": null,
    "experience_mentioned": "true",
    "experience_preferred": "false"
  },
  "job_required_skills": null,
  "job_required_education": {
    "postgraduate_degree": "false",
    "professional_certification": "false",
    "high_school": "false",
    "associates_degree": "false",
    "bachelors_degree": "true",
    "degree_mentioned": "false",
    "degree_preferred": "false",
    "professional_certification_mentioned": "false"
  },
  "job_experience_in_place_of_education": false,
  "job_min_salary": null,
  "job_max_salary": null,
  "job_salary_currency": null,
  "job_salary_period": null,
  "job_highlights": {
    "Qualifications": [
      "Great gaming development history",
      "Experience with JavaScript",
      "Extensive experience with Node.js",
      "Knowledge of AWS microservices"
    ],
    "Responsibilities": [
      "Development of matchmaking service",
      "Working on the identity service"
    ]
  },
  "job_job_title": "Senior",
  "job_posting_language": "en",
  "job_onet_soc": "15113400",
  "job_onet_job_zone": "3",
  "job_occupational_categories": null,
  "job_naics_code": "541511",
  "job_naics_name": "Custom Computer Programming Services"
}

| Field                                  | Type    | Description                                                      |                                                                |
| -------------------------------------- | ------- | ---------------------------------------------------------------- | -------------------------------------------------------------- |
| `job_id`                               | string  | Unique identifier of the job posting.                            |                                                                |
| `employer_name`                        | string  | Company/employer name.                                           |                                                                |
| `employer_logo`                        | string  | null                                                             | URL to employer’s logo image.                                  |
| `employer_website`                     | string  | null                                                             | Employer’s website URL.                                        |
| `employer_company_type`                | string  | null                                                             | Description of employer’s company type (industry/sector).      |
| `employer_linkedin`                    | string  | null                                                             | URL to employer’s LinkedIn page (if available).                |
| `job_publisher`                        | string  | Source of the job listing (e.g., LinkedIn).                      |                                                                |
| `job_employment_type`                  | string  | Employment type (e.g., FULLTIME, CONTRACT).                      |                                                                |
| `job_title`                            | string  | Title of the job role.                                           |                                                                |
| `job_apply_link`                       | string  | Link where candidate can apply.                                  |                                                                |
| `job_apply_is_direct`                  | boolean | Indicates if apply link is direct to employer or via aggregator. |                                                                |
| `job_apply_quality_score`              | number  | Score representing quality of the apply link.                    |                                                                |
| `apply_options`                        | array   | Alternative apply links with publishers and is_direct flags.     |                                                                |
| `job_description`                      | string  | Full text description of the job.                                |                                                                |
| `job_is_remote`                        | boolean | Whether the job is remote (true) or not (false).                 |                                                                |
| `job_posted_at_timestamp`              | integer | Unix timestamp when job was posted.                              |                                                                |
| `job_posted_at_datetime_utc`           | string  | ISO8601 UTC date-time when job was posted.                       |                                                                |
| `job_city`, `job_state`, `job_country` | string  | null                                                             | Location of the job.                                           |
| `job_latitude`, `job_longitude`        | number  | null                                                             | Geolocation of job posting.                                    |
| `job_benefits`                         | string  | null                                                             | Benefits text (if available).                                  |
| `job_google_link`                      | string  | null                                                             | Link to the Google for Jobs view of the posting.               |
| `job_offer_expiration_datetime_utc`    | string  | null                                                             | ISO8601 UTC date-time when job offer expires.                  |
| `job_offer_expiration_timestamp`       | integer | null                                                             | Unix timestamp for offer expiration.                           |
| `job_required_experience`              | object  | Object describing experience requirements.                       |                                                                |
| `job_required_skills`                  | array   | null                                                             | Array of skills (if provided).                                 |
| `job_required_education`               | object  | Object describing education requirements.                        |                                                                |
| `job_experience_in_place_of_education` | boolean | Flag if experience counts in lieu of education.                  |                                                                |
| `job_min_salary`, `job_max_salary`     | number  | null                                                             | Salary bounds (if provided).                                   |
| `job_salary_currency`                  | string  | null                                                             | Currency code for salary.                                      |
| `job_salary_period`                    | string  | null                                                             | Salary period (e.g., YEAR, HOUR).                              |
| `job_highlights`                       | object  | null                                                             | Highlights breakdown (Qualifications, Responsibilities, etc.). |
| `job_job_title`                        | string  | null                                                             | Short title category or level (e.g., “Senior”).                |
| `job_posting_language`                 | string  | Language code of the posting (e.g., “en”).                       |                                                                |
| `job_onet_soc`                         | string  | null                                                             | ONET (SOC) code for the job.                                   |
| `job_onet_job_zone`                    | string  | null                                                             | ONET job zone classification.                                  |
| `job_occupational_categories`          | array   | null                                                             | Occupational category list.                                    |
| `job_naics_code`                       | string  | null                                                             | NAICS industry code.                                           |
| `job_naics_name`                       | string  | null                                                             | Description of NAICS industry.                                 |


Common Status Codes & Error Handling

200 OK — request succeeded, data returned.

401 Unauthorized — invalid or missing API key.

404 Not Found — e.g., job_id not found or job expired.

429 Too Many Requests — rate limit exceeded.

500 Internal Server Error / 503 Service Unavailable — retry logic recommended.