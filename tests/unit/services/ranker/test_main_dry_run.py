from services.ranker.config_loader import RankingConfig, RankingWeights, UserProfile, SalaryTarget
from services.ranker.main import run_ranker


class FakeDB:
    def __init__(self, jobs):
        self._jobs = jobs
        self.updated = []

    def fetch_unranked_jobs(self, limit=None, where_rank_score_is_null=True):
        return self._jobs[: limit or None]

    def update_jobs_ranking_batch(self, rankings):
        self.updated.extend(rankings)
        return len(rankings)

    def get_ranking_stats(self):
        # Very basic stats for test purposes
        return {
            'total_jobs': len(self._jobs),
            'ranked_jobs': len(self.updated),
            'unranked_jobs': len(self._jobs) - len(self.updated),
            'average_score': sum(r['rank_score'] for r in self.updated) / len(self.updated) if self.updated else None,
            'top_score': max((r['rank_score'] for r in self.updated), default=None),
            'bottom_score': min((r['rank_score'] for r in self.updated), default=None),
        }


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


def test_run_ranker_with_fake_db():
    config = make_config()
    jobs = [
        {
            'hash_key': 'a',
            'job_title_std': 'Junior Data Engineer',
            'skills': ['SQL', 'Python', 'Airflow'],
            'location_std': 'Montreal, QC, CA',
            'salary_min_norm': 80000,
            'salary_max_norm': 100000,
            'remote_type': 'hybrid',
            'contract_type': 'full_time',
            'company_size': '201-500',
        },
        {
            'hash_key': 'b',
            'job_title_std': 'Senior Backend Developer',
            'skills': ['Java', 'Kotlin'],
            'location_std': 'Toronto, ON, CA',
            'salary_min_norm': 130000,
            'salary_max_norm': 150000,
            'remote_type': 'onsite',
            'contract_type': 'contract',
            'company_size': 'unknown',
        },
    ]

    fake_db = FakeDB(jobs)

    stats = run_ranker(
        db=fake_db,  # type: ignore[arg-type]
        config=config,
        limit=None,
        re_rank_all=False,
        dry_run=False,
    )

    assert stats['fetched'] == 2
    assert stats['ranked'] == 2
    assert stats['failed'] == 0

    # Ensure updates were applied
    assert len(fake_db.updated) == 2
    for r in fake_db.updated:
        assert r['hash_key'] in {'a', 'b'}
        assert 0 <= r['rank_score'] <= 100
