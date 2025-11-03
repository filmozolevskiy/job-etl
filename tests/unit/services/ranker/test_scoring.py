import math
import pytest

from services.ranker.config_loader import RankingConfig, RankingWeights, UserProfile, SalaryTarget
from services.ranker.scoring import calculate_rank


def make_config() -> RankingConfig:
    weights = RankingWeights(
        title_keywords=0.25,
        skills_overlap=0.30,
        location_proximity=0.10,
        salary_band=0.15,
        employment_type=0.05,
        seniority_match=0.07,
        remote_type=0.04,
        company_size=0.04,
    )
    profile = UserProfile(
        title_keywords=["data engineer", "etl"],
        must_have_skills=["sql", "python"],
        nice_to_have_skills=["airflow", "dbt"],
        location_home="Montreal, QC, CA",
        location_radius_km=50,
        salary_target_cad=SalaryTarget(min=70000, max=120000),
        preferred_remote=["remote", "hybrid"],
        preferred_contracts=["full_time"],
        seniority=["junior", "intermediate"],
        preferred_company_sizes=["201-500", "501-1000"],
    )
    return RankingConfig(weights=weights, profile=profile)


def test_calculate_rank_happy_path():
    config = make_config()
    job = {
        'hash_key': 'abc',
        'job_title_std': 'Junior Data Engineer',
        'skills': ['SQL', 'Python', 'Airflow'],
        'location_std': 'Montreal, QC, CA',
        'salary_min_norm': 80000,
        'salary_max_norm': 100000,
        'remote_type': 'hybrid',
        'contract_type': 'full_time',
        'company_size': '201-500',
    }

    score, explain = calculate_rank(job, config)

    assert 0 <= score <= 100
    # Expect reasonably high score due to many matches
    assert score > 70
    # Per-feature keys present
    for key in [
        'title_keywords', 'skills_overlap', 'location_proximity', 'salary_band',
        'employment_type', 'seniority_match', 'remote_type', 'company_size'
    ]:
        assert key in explain
        assert 0.0 <= explain[key] <= 1.0


def test_calculate_rank_missing_must_have_skills_penalized():
    config = make_config()
    job = {
        'hash_key': 'def',
        'job_title_std': 'Data Engineer',
        'skills': ['airflow'],  # missing sql/python
        'location_std': 'Toronto, ON, CA',
        'salary_min_norm': 60000,
        'salary_max_norm': 65000,
        'remote_type': 'onsite',
        'contract_type': 'contract',
        'company_size': 'unknown',
    }

    score, explain = calculate_rank(job, config)

    assert 0 <= score <= 100
    # Expect lower score due to penalties
    assert score < 50
    assert explain['skills_overlap'] <= 0.2
