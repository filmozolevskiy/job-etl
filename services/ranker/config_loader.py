"""
Configuration Loader for Ranker Service

This module loads and validates the ranking configuration from ranking.yml.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml

logger = logging.getLogger(__name__)


@dataclass
class RankingWeights:
    """Weights for ranking features."""

    title_keywords: float = 0.25
    skills_overlap: float = 0.30
    location_proximity: float = 0.10
    salary_band: float = 0.15
    employment_type: float = 0.05
    seniority_match: float = 0.07
    remote_type: float = 0.04
    company_size: float = 0.04

    def validate(self) -> None:
        """Validate that weights sum to approximately 1.0."""
        total = sum([
            self.title_keywords,
            self.skills_overlap,
            self.location_proximity,
            self.salary_band,
            self.employment_type,
            self.seniority_match,
            self.remote_type,
            self.company_size,
        ])
        if not (0.95 < total < 1.05):  # Allow small rounding errors
            logger.warning(
                f"Weights sum to {total:.2f}, expected ~1.0",
                extra={'weights_sum': total}
            )


@dataclass
class SalaryTarget:
    """Salary target range."""

    min: float
    max: float


@dataclass
class UserProfile:
    """User profile preferences."""

    title_keywords: list[str]
    must_have_skills: list[str]
    nice_to_have_skills: list[str]
    location_home: str
    location_radius_km: int
    salary_target_cad: SalaryTarget
    preferred_remote: list[str]
    preferred_contracts: list[str]
    seniority: list[str]
    preferred_company_sizes: list[str]


@dataclass
class RankingConfig:
    """Complete ranking configuration."""

    weights: RankingWeights
    profile: UserProfile

    @classmethod
    def from_dict(cls, config_dict: dict[str, Any]) -> "RankingConfig":
        """Create RankingConfig from dictionary."""
        # Parse weights
        weights_dict = config_dict.get("weights", {})
        weights = RankingWeights(
            title_keywords=weights_dict.get("title_keywords", 0.25),
            skills_overlap=weights_dict.get("skills_overlap", 0.30),
            location_proximity=weights_dict.get("location_proximity", 0.10),
            salary_band=weights_dict.get("salary_band", 0.15),
            employment_type=weights_dict.get("employment_type", 0.05),
            seniority_match=weights_dict.get("seniority_match", 0.07),
            remote_type=weights_dict.get("remote_type", 0.04),
            company_size=weights_dict.get("company_size", 0.04),
        )
        weights.validate()

        # Parse profile
        profile_dict = config_dict.get("profile", {})
        salary_dict = profile_dict.get("salary_target_cad", {"min": 70000, "max": 120000})
        salary_target = SalaryTarget(
            min=float(salary_dict["min"]),
            max=float(salary_dict["max"])
        )

        profile = UserProfile(
            title_keywords=profile_dict.get("title_keywords", []),
            must_have_skills=profile_dict.get("must_have_skills", []),
            nice_to_have_skills=profile_dict.get("nice_to_have_skills", []),
            location_home=profile_dict.get("location_home", ""),
            location_radius_km=profile_dict.get("location_radius_km", 50),
            salary_target_cad=salary_target,
            preferred_remote=profile_dict.get("preferred_remote", []),
            preferred_contracts=profile_dict.get("preferred_contracts", []),
            seniority=profile_dict.get("seniority", []),
            preferred_company_sizes=profile_dict.get("preferred_company_sizes", []),
        )

        return cls(weights=weights, profile=profile)


def load_ranking_config(config_path: Optional[str] = None) -> RankingConfig:
    """
    Load ranking configuration from YAML file.

    Args:
        config_path: Path to ranking.yml file. If None, uses default location.

    Returns:
        RankingConfig object with weights and profile

    Raises:
        FileNotFoundError: If config file doesn't exist
        ValueError: If config is invalid

    Example:
        >>> config = load_ranking_config('config/ranking.yml')
        >>> print(config.weights.title_keywords)
        0.25
    """
    if config_path is None:
        # Default path relative to project root
        project_root = Path(__file__).parent.parent.parent
        config_path = str(project_root / "config" / "ranking.yml")

    logger.info("Loading ranking configuration", extra={'config_path': config_path})

    try:
        with open(config_path) as f:
            config_dict = yaml.safe_load(f)

        if not config_dict:
            logger.warning("Empty configuration file, using defaults")
            config_dict = {}

        config = RankingConfig.from_dict(config_dict)

        logger.info(
            "Ranking configuration loaded successfully",
            extra={
                'weights_sum': sum([
                    config.weights.title_keywords,
                    config.weights.skills_overlap,
                    config.weights.location_proximity,
                    config.weights.salary_band,
                    config.weights.employment_type,
                    config.weights.seniority_match,
                    config.weights.remote_type,
                    config.weights.company_size,
                ]),
                'profile_title_keywords': len(config.profile.title_keywords),
                'must_have_skills': len(config.profile.must_have_skills),
            }
        )

        return config

    except FileNotFoundError:
        logger.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logger.error(f"Failed to parse YAML: {e}")
        raise ValueError(f"Invalid YAML in config file: {e}") from e
    except Exception as e:
        logger.error(f"Failed to load configuration: {e}")
        raise ValueError(f"Failed to load configuration: {e}") from e

