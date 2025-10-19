"""Job-ETL Microservices Package.

This package contains all microservices for the Job-ETL pipeline:
- source-extractor: Fetches job postings from external APIs
- normalizer: Normalizes data to canonical format
- enricher: Enriches data with skills, location, etc.
- ranker: Ranks jobs based on user preferences
- publisher-hyper: Publishes to Tableau Hyper format
"""

__version__ = "0.1.0"

