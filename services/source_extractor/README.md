# Source Extractor Service

The Source Extractor service fetches job postings from external APIs and stores the raw JSON responses for further processing.

## Architecture

### Components

1. **SourceAdapter (base.py)**: Abstract base class defining the interface all adapters must implement
2. **Adapters (adapters/)**: Concrete implementations for specific job APIs
3. **Retry Logic (retry.py)**: Exponential backoff for handling transient failures

### Design Pattern

The Source Extractor uses the **Adapter Pattern** to provide a uniform interface for different job posting APIs:

```
┌─────────────────┐
│  SourceAdapter  │  ← Abstract Base Class
│  (Interface)    │
└────────┬────────┘
         │
         ├──────────────────┬──────────────────┬───────────────
         │                  │                  │
┌────────▼────────┐ ┌───────▼─────────┐ ┌─────▼──────┐
│  MockAdapter    │ │  RapidAPIAdapter│ │  IndeedAPI │
│  (for testing)  │ │  (real API)     │ │  (future)  │
└─────────────────┘ └─────────────────┘ └────────────┘
```

## Usage

### Implementing a New Adapter

```python
from services.source_extractor import SourceAdapter, JobPostingRaw

class MyAPIAdapter(SourceAdapter):
    def __init__(self, api_key: str):
        super().__init__(source_name="my_api")
        self.api_key = api_key
    
    def fetch(self, page_token=None):
        # Implement API fetching logic
        response = requests.get(
            "https://api.example.com/jobs",
            headers={"Authorization": f"Bearer {self.api_key}"},
            params={"page": page_token or 0}
        )
        
        jobs = []
        for job_data in response.json()["jobs"]:
            jobs.append(JobPostingRaw(
                source=self.source_name,
                payload=job_data,
                provider_job_id=job_data.get("id")
            ))
        
        next_token = response.json().get("next_page")
        return jobs, next_token
    
    def map_to_common(self, raw):
        # Map provider fields to our canonical schema
        return {
            "job_title": raw.payload["title"],
            "company": raw.payload["company_name"],
            # ... map other fields ...
            "source": self.source_name,
        }
```

### Using an Adapter

```python
from services.source_extractor.adapters.mock_adapter import MockAdapter

# Create adapter
adapter = MockAdapter(num_jobs=100)

# Fetch first page
jobs, next_token = adapter.fetch()
print(f"Fetched {len(jobs)} jobs")

# Fetch next page
if next_token:
    more_jobs, next_token = adapter.fetch(next_token)
    jobs.extend(more_jobs)

# Map to canonical format
for job in jobs:
    common_format = adapter.map_to_common(job)
    print(common_format["job_title"], "-", common_format["company"])
```

### Using Retry Logic

```python
from services.source_extractor.retry import retry_api_call

@retry_api_call(max_retries=3)
def fetch_with_retry():
    # This will automatically retry on ConnectionError, TimeoutError
    return adapter.fetch()

jobs, next_token = fetch_with_retry()
```

## Data Flow

```
External API
     ↓
  [fetch()]  ← Fetches raw JSON with pagination
     ↓
JobPostingRaw  ← Stores raw response + metadata
     ↓
[map_to_common()]  ← Transforms to canonical format
     ↓
staging.job_postings_stg  ← Ready for dbt processing
```

## Testing

### Running Tests

```bash
# Run all source adapter tests
pytest tests/unit/test_source_adapter.py -v

# Run retry logic tests
pytest tests/unit/test_retry_logic.py -v

# Run specific test
pytest tests/unit/test_source_adapter.py::TestSourceAdapterContract::test_fetch_returns_correct_type -v
```

### Contract Tests

The contract tests (`TestSourceAdapterContract`) verify that any adapter implementation:
- Returns correct types from `fetch()`
- Implements pagination correctly
- Maps data to canonical format with required fields
- Validates enum values (remote_type, contract_type)

**To test a new adapter**, just override the `adapter` fixture:

```python
@pytest.fixture
def adapter(self) -> SourceAdapter:
    return MyNewAdapter(api_key="test_key")
```

## Configuration

Add new providers to `config/sources.yml`:

```yaml
providers:
  my_api:
    adapter_class: "MyAPIAdapter"
    api_key: ${MY_API_KEY}  # From environment variable
    rate_limit: 100  # requests per minute
    timeout: 30  # seconds
```

## Error Handling

The service handles several error scenarios:

1. **Network Failures**: Automatic retry with exponential backoff
2. **Rate Limiting**: Respects API rate limits (implemented per adapter)
3. **Invalid Data**: Validates data before storing
4. **API Errors**: Logs errors and continues with other sources

## Future Enhancements

- [ ] Add real API adapters (RapidAPI, Indeed, etc.)
- [ ] Implement rate limiting per provider
- [ ] Add caching for API responses
- [ ] Support for API authentication methods (OAuth, API key, Bearer token)
- [ ] Metrics and monitoring (requests per second, error rates)

