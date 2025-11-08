"""
Source configuration loader for the source-extractor service.

This module centralizes reading and validating source extraction settings from
`config/sources.yml`. All microservices (Airflow DAG, CLI utilities, tests)
should use this helper to keep configuration handling consistent.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


@dataclass
class ProviderConfig:
    """Configuration for a single source provider."""

    adapter: str
    enabled: bool = True
    params: dict[str, Any] = field(default_factory=dict)


def _project_root() -> Path:
    """Return the project root path based on this file's location."""
    return Path(__file__).resolve().parent.parent.parent


def load_sources_config(config_path: str | None = None) -> dict[str, ProviderConfig]:
    """
    Load provider configuration from YAML file.

    Args:
        config_path: Optional override for the config file path. When omitted,
            the function reads `config/sources.yml` relative to the project root.

    Returns:
        Dictionary mapping provider names to `ProviderConfig` objects.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        ValueError: If the YAML file cannot be parsed or has invalid structure.
    """
    path = Path(config_path) if config_path else _project_root() / "config" / "sources.yml"
    if not path.exists():
        logger.error("Sources configuration file not found: %s", path)
        raise FileNotFoundError(f"Sources configuration file not found: {path}")

    try:
        with path.open("r", encoding="utf-8") as handle:
            raw_config: Mapping[str, Any] | None = yaml.safe_load(handle)
    except yaml.YAMLError as exc:
        logger.error("Failed to parse sources configuration: %s", exc)
        raise ValueError(f"Invalid YAML in sources configuration: {exc}") from exc

    if not raw_config:
        logger.warning("Sources configuration file is empty: %s", path)
        return {}

    providers_section = raw_config.get("providers")
    if not isinstance(providers_section, Mapping):
        raise ValueError("`providers` section is missing or invalid in sources configuration")

    providers: dict[str, ProviderConfig] = {}
    for provider_name, provider_data in providers_section.items():
        if not isinstance(provider_data, Mapping):
            raise ValueError(f"Invalid provider configuration for '{provider_name}'")

        adapter = provider_data.get("adapter")
        if not isinstance(adapter, str) or not adapter.strip():
            raise ValueError(f"Provider '{provider_name}' must define a non-empty `adapter` string")

        enabled = bool(provider_data.get("enabled", True))
        params = provider_data.get("params", {})
        if params and not isinstance(params, Mapping):
            raise ValueError(f"`params` for provider '{provider_name}' must be a mapping")

        providers[provider_name] = ProviderConfig(
            adapter=adapter,
            enabled=enabled,
            params=dict(params),
        )

    logger.info(
        "Loaded sources configuration",
        extra={
            "sources_count": len(providers),
            "enabled_sources": [name for name, cfg in providers.items() if cfg.enabled],
        },
    )
    return providers


__all__ = ["ProviderConfig", "load_sources_config"]

