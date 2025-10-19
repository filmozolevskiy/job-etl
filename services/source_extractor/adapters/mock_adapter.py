"""Mock Adapter for Testing.

This adapter simulates an external job API for testing purposes.
It doesn't make real HTTP requests, but follows the same patterns.
"""

from typing import Any, Optional

from ..base import JobPostingRaw, SourceAdapter


class MockAdapter(SourceAdapter):
    """Mock adapter that returns fake job postings for testing.

    This adapter is useful for:
    - Unit testing without hitting real APIs
    - Demonstrating how to implement SourceAdapter
    - Testing error handling and retry logic

    Example:
        adapter = MockAdapter(num_jobs=50, jobs_per_page=10)
        jobs, next_token = adapter.fetch()
        assert len(jobs) == 10
        assert next_token is not None

        more_jobs, next_token = adapter.fetch(next_token)
        assert len(more_jobs) == 10
    """

    def __init__(
        self, num_jobs: int = 100, jobs_per_page: int = 20, fail_on_attempt: int = 0
    ):
        """Initialize the mock adapter.

        Args:
            num_jobs: Total number of fake jobs to generate
            jobs_per_page: Number of jobs to return per page
            fail_on_attempt: If > 0, fail on this attempt number (for testing retries)
        """
        super().__init__(source_name="mock_api")
        self.num_jobs = num_jobs
        self.jobs_per_page = jobs_per_page
        self.fail_on_attempt = fail_on_attempt
        self.attempt_count = 0

    def fetch(
        self, page_token: Optional[str] = None
    ) -> tuple[list[JobPostingRaw], Optional[str]]:
        """Fetch fake job postings.

        Args:
            page_token: Page number as string (e.g., "1", "2") or None for first page

        Returns:
            Tuple of (list of JobPostingRaw, next page token)
        """
        # Simulate failure for testing retry logic
        self.attempt_count += 1
        if self.fail_on_attempt > 0 and self.attempt_count == self.fail_on_attempt:
            raise ConnectionError("Simulated API failure for testing")

        # Determine current page
        current_page = 0 if page_token is None else int(page_token)

        # Calculate which jobs to return
        start_idx = current_page * self.jobs_per_page
        end_idx = min(start_idx + self.jobs_per_page, self.num_jobs)

        # Generate fake jobs
        jobs = []
        for i in range(start_idx, end_idx):
            job_data = self._generate_fake_job(i)
            jobs.append(
                JobPostingRaw(
                    source=self.source_name,
                    payload=job_data,
                    provider_job_id=f"mock_{i}",
                )
            )

        # Determine next page token
        next_page = current_page + 1
        has_more = end_idx < self.num_jobs
        next_token = str(next_page) if has_more else None

        return jobs, next_token

    def map_to_common(self, raw: JobPostingRaw) -> dict[str, Any]:
        """Map mock job data to canonical format.

        Args:
            raw: JobPostingRaw with mock job data

        Returns:
            Dictionary matching staging.job_postings_stg schema
        """
        payload = raw.payload

        return {
            "provider_job_id": raw.provider_job_id,
            "job_link": payload.get("job_url"),
            "job_title": payload["title"],
            "company": payload["company"],
            "company_size": payload.get("company_size"),
            "location": payload["location"],
            "remote_type": payload.get("remote_type", "unknown"),
            "contract_type": payload.get("contract_type", "full_time"),
            "salary_min": payload.get("salary_min"),
            "salary_max": payload.get("salary_max"),
            "salary_currency": payload.get("salary_currency"),
            "description": payload.get("description"),
            "skills_raw": payload.get("skills", []),
            "posted_at": payload.get("posted_date"),
            "apply_url": payload.get("apply_url"),
            "source": self.source_name,
        }

    def _generate_fake_job(self, index: int) -> dict[str, Any]:
        """Generate a fake job posting.

        Args:
            index: Job index for unique data

        Returns:
            Dictionary with fake job data
        """
        job_titles = [
            "Data Engineer",
            "Analytics Engineer",
            "Data Scientist",
            "Machine Learning Engineer",
            "Data Analyst",
            "ETL Developer",
        ]

        companies = [
            "Acme Corp",
            "Globex Inc",
            "Initech LLC",
            "Umbrella Corporation",
            "Wayne Enterprises",
        ]

        locations = [
            "Montreal, QC, Canada",
            "Toronto, ON, Canada",
            "Vancouver, BC, Canada",
            "Remote",
            "New York, NY, USA",
        ]

        remote_types = ["remote", "hybrid", "onsite"]
        contract_types = ["full_time", "part_time", "contract"]

        # Use modulo to cycle through options
        title = job_titles[index % len(job_titles)]
        company = companies[index % len(companies)]
        location = locations[index % len(locations)]
        remote_type = remote_types[index % len(remote_types)]
        contract_type = contract_types[index % len(contract_types)]

        return {
            "title": f"{title}",
            "company": company,
            "location": location,
            "remote_type": remote_type,
            "contract_type": contract_type,
            "salary_min": 70000 + (index * 1000 % 50000),
            "salary_max": 120000 + (index * 1000 % 50000),
            "salary_currency": "CAD",
            "description": f"We are seeking a {title} to join our team at {company}. "
            f"This is a {remote_type} position. "
            f"You will work with Python, SQL, and various data tools.",
            "skills": ["python", "sql", "airflow", "dbt"],
            "posted_date": "2025-10-15T10:00:00Z",
            "job_url": f"https://example.com/jobs/{index}",
            "apply_url": f"https://example.com/apply/{index}",
            "company_size": "51-200",
        }

