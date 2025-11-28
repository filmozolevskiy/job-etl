"""
Scoring Algorithm for Ranker Service

This module contains the core ranking logic that calculates job scores based on
configurable weights and user profile preferences.
"""

import logging
from typing import Any, Optional

from .config_loader import RankingConfig

logger = logging.getLogger(__name__)


def calculate_title_score(job_title: str, title_keywords: list[str]) -> float:
    """
    Calculate score for title keyword matching.

    Simple substring matching approach for MVP.
    More sophisticated NLP matching to be added in Phase 1.

    Args:
        job_title: The job title to analyze
        title_keywords: List of keywords to match against

    Returns:
        Score between 0 and 1
    """
    if not job_title or not title_keywords:
        return 0.0

    job_title_lower = job_title.lower()
    matches = sum(1 for keyword in title_keywords if keyword.lower() in job_title_lower)
    total_keywords = len(title_keywords)

    score = matches / total_keywords if total_keywords > 0 else 0.0
    logger.debug(
        "Title score calculated",
        extra={
            'job_title': job_title,
            'matches': matches,
            'total_keywords': total_keywords,
            'score': score,
        }
    )
    return score


def calculate_skills_score(
    job_skills: list[str],
    must_have_skills: list[str],
    nice_to_have_skills: list[str]
) -> float:
    """
    Calculate score for skills overlap.

    Uses Jaccard similarity with weighted boost for must-have skills.

    Args:
        job_skills: Skills from the job posting
        must_have_skills: Required skills
        nice_to_have_skills: Optional skills

    Returns:
        Score between 0 and 1
    """
    if not job_skills:
        return 0.0

    job_skills_lower = [skill.lower() for skill in job_skills]
    must_have_lower = [skill.lower() for skill in must_have_skills]
    nice_to_have_lower = [skill.lower() for skill in nice_to_have_skills]

    # Check for must-have skills (fail if any missing)
    must_have_matches = sum(1 for skill in must_have_lower if skill in job_skills_lower)
    if must_have_matches < len(must_have_lower):
        # Missing required skills - penalize heavily
        return 0.1  # Small non-zero score to not eliminate entirely

    # Calculate Jaccard similarity for nice-to-have skills
    nice_to_have_matches = sum(1 for skill in nice_to_have_lower if skill in job_skills_lower)
    if not nice_to_have_lower:
        # No nice-to-have skills defined, just having must-haves is good
        return 0.8
    else:
        nice_to_have_score = nice_to_have_matches / len(nice_to_have_lower)
        # Base score from must-haves plus bonus from nice-to-haves
        score = 0.5 + (0.5 * nice_to_have_score)

    logger.debug(
        "Skills score calculated",
        extra={
            'must_have_matches': must_have_matches,
            'nice_to_have_matches': nice_to_have_matches,
            'score': score,
        }
    )
    return score


def calculate_location_score(location: str, location_home: str) -> float:
    """
    Calculate score for location proximity.

    MVP: Simple exact match. Geospatial distance in Phase 1.

    Args:
        location: Job location
        location_home: User's home location

    Returns:
        Score between 0 and 1
    """
    if not location or not location_home:
        return 0.0

    if location.lower() == location_home.lower():
        return 1.0

    # Check if same city (simple substring check)
    location_parts = location.lower().split(',')
    home_parts = location_home.lower().split(',')
    if location_parts and home_parts and location_parts[0].strip() == home_parts[0].strip():
        return 0.7

    # Check for 'remote' keyword
    if 'remote' in location.lower():
        return 0.5  # Partially score for remote jobs

    return 0.0


def calculate_salary_score(
    salary_min: Optional[float],
    salary_max: Optional[float],
    salary_target_min: float,
    salary_target_max: float
) -> float:
    """
    Calculate score based on salary range.

    Args:
        salary_min: Minimum salary from job posting
        salary_max: Maximum salary from job posting
        salary_target_min: User's minimum target salary
        salary_target_max: User's maximum target salary

    Returns:
        Score between 0 and 1
    """
    # Normalize numeric types (database may return Decimal)
    try:
        if salary_min is not None:
            salary_min = float(salary_min)
        if salary_max is not None:
            salary_max = float(salary_max)
        if salary_target_min is not None:
            salary_target_min = float(salary_target_min)
        if salary_target_max is not None:
            salary_target_max = float(salary_target_max)
    except Exception:
        # If conversion fails, fall back to neutral score
        return 0.5

    if not salary_min and not salary_max:
        return 0.5  # No salary info - neutral score

    # Use average if both min and max are present
    if salary_min and salary_max:
        salary_avg = (salary_min + salary_max) / 2
    elif salary_min:
        salary_avg = salary_min
    elif salary_max:
        salary_avg = salary_max
    else:
        return 0.5

    # Check if within target range
    if salary_target_min <= salary_avg <= salary_target_max:
        return 1.0

    # Calculate penalty for being outside range
    if salary_avg < salary_target_min:
        # Below minimum - taper based on how far below
        distance = salary_target_min - salary_avg
        range_size = salary_target_max - salary_target_min
        penalty = min(distance / range_size, 1.0)
        return max(0.1, 1.0 - penalty)
    else:
        # Above maximum - taper based on how far above
        distance = salary_avg - salary_target_max
        range_size = salary_target_max - salary_target_min
        penalty = min(distance / range_size, 1.0)
        return max(0.1, 1.0 - penalty)


def calculate_remote_score(remote_type: str, preferred_remote: list[str]) -> float:
    """
    Calculate score for remote type preference.

    Args:
        remote_type: Job remote type (remote, hybrid, onsite, unknown)
        preferred_remote: User's preferred remote types

    Returns:
        Score between 0 and 1
    """
    if not remote_type or remote_type == 'unknown':
        return 0.5  # Unknown - neutral score

    if remote_type.lower() in [p.lower() for p in preferred_remote]:
        return 1.0

    return 0.0


def calculate_contract_score(contract_type: str, preferred_contracts: list[str]) -> float:
    """
    Calculate score for contract type preference.

    Args:
        contract_type: Job contract type
        preferred_contracts: User's preferred contract types

    Returns:
        Score between 0 and 1
    """
    if not contract_type or contract_type == 'unknown':
        return 0.5  # Unknown - neutral score

    if contract_type.lower() in [p.lower() for p in preferred_contracts]:
        return 1.0

    return 0.3  # Some penalty but not zero


def calculate_seniority_score(
    seniority_level: Optional[str],
    seniority_preferences: list[str],
) -> float:
    """
    Calculate score based on job seniority.

    Uses the precomputed ``seniority_level`` from the data mart.

    Args:
        seniority_level: Seniority level string from marts.fact_jobs
        seniority_preferences: User's preferred seniority levels

    Returns:
        Score between 0 and 1
    """
    level = (seniority_level or "unknown").lower()

    # If seniority cannot be determined, return neutral score
    if level == 'unknown':
        return 0.5  # Can't determine - neutral

    # Check if detected seniority matches user preferences
    if level in [s.lower() for s in seniority_preferences]:
        return 1.0

    return 0.3  # Not preferred but not eliminated


def calculate_company_size_score(
    company_size: str,
    preferred_sizes: list[str]
) -> float:
    """
    Calculate score for company size preference.

    Args:
        company_size: Job company size
        preferred_sizes: User's preferred company sizes

    Returns:
        Score between 0 and 1
    """
    if not company_size or company_size == 'unknown':
        return 0.5  # Unknown - neutral score

    if company_size in preferred_sizes:
        return 1.0

    return 0.7  # Not preferred but acceptable


def calculate_rank(job: dict[str, Any], config: RankingConfig) -> tuple[float, dict[str, float]]:
    """
    Calculate overall ranking score for a job posting.

    Args:
        job: Job posting data from marts.fact_jobs
        config: Ranking configuration with weights and profile

    Returns:
        Tuple of (rank_score, rank_explain_dict)
        - rank_score: Overall score (0-100)
        - rank_explain_dict: Per-feature subscores

    Example:
        >>> score, explain = calculate_rank(job_dict, config)
        >>> print(f"Score: {score:.2f}")
        >>> print(explain)
    """
    # Calculate per-feature scores
    title_score = calculate_title_score(
        job.get('job_title_std', ''),
        config.profile.title_keywords
    )

    skills = job.get('skills', []) if isinstance(job.get('skills'), list) else []
    skills_score = calculate_skills_score(
        skills,
        config.profile.must_have_skills,
        config.profile.nice_to_have_skills
    )

    location_score = calculate_location_score(
        job.get('location_std', ''),
        config.profile.location_home
    )

    salary_score = calculate_salary_score(
        job.get('salary_min_norm'),
        job.get('salary_max_norm'),
        config.profile.salary_target_cad.min,
        config.profile.salary_target_cad.max
    )

    remote_score = calculate_remote_score(
        job.get('remote_type', 'unknown'),
        config.profile.preferred_remote
    )

    contract_score = calculate_contract_score(
        job.get('contract_type', 'unknown'),
        config.profile.preferred_contracts
    )

    seniority_score = calculate_seniority_score(
        job.get('seniority_level'),
        config.profile.seniority,
    )

    company_size_score = calculate_company_size_score(
        job.get('company_size', 'unknown') if 'company_size' in job else 'unknown',
        config.profile.preferred_company_sizes
    )

    # Calculate weighted sum
    weighted_score = (
        config.weights.title_keywords * title_score +
        config.weights.skills_overlap * skills_score +
        config.weights.location_proximity * location_score +
        config.weights.salary_band * salary_score +
        config.weights.employment_type * contract_score +
        config.weights.seniority_match * seniority_score +
        config.weights.remote_type * remote_score +
        config.weights.company_size * company_size_score
    )

    # Scale to 0-100 and normalize (round to 2 decimal places, clamp to 0-100)
    rank_score = weighted_score * 100
    rank_score = max(0.0, min(100.0, round(rank_score, 2)))

    # Build explain dict
    rank_explain = {
        'title_keywords': title_score,
        'skills_overlap': skills_score,
        'location_proximity': location_score,
        'salary_band': salary_score,
        'employment_type': contract_score,
        'seniority_match': seniority_score,
        'remote_type': remote_score,
        'company_size': company_size_score,
    }

    logger.debug(
        "Rank score calculated",
        extra={
            'hash_key': job.get('hash_key'),
            'rank_score': rank_score,
            'explain': rank_explain,
        }
    )

    return rank_score, rank_explain


