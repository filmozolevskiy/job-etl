"""
Tests for the SkillsExtractor helper.

The tests intentionally use a lightweight dictionary to avoid depending on the
repository configuration file.  This keeps the tests focused on behaviour.
"""
from __future__ import annotations

from services.enricher.skills_extractor import (
    SkillEntry,
    SkillsDictionary,
    SkillsExtractor,
)


def _make_dictionary() -> SkillsDictionary:
    entries = [
        SkillEntry(name="python", aliases=("python", "python3")),
        SkillEntry(name="sql", aliases=("sql",)),
        SkillEntry(name="airflow", aliases=("airflow", "apache airflow")),
        SkillEntry(name="dbt", aliases=("dbt", "data build tool")),
    ]
    return SkillsDictionary(entries)


def test_extract_combines_description_and_existing_skills() -> None:
    extractor = SkillsExtractor(dictionary=_make_dictionary())

    description = "We build pipelines with Apache Airflow, dbt and Python."
    existing = ["SQL"]

    result = extractor.extract(description, existing)

    assert result == ["airflow", "dbt", "python", "sql"]


def test_extract_deduplicates_and_normalises() -> None:
    extractor = SkillsExtractor(dictionary=_make_dictionary())

    description = "Python python PYTHON."
    existing = ["Python", "python3", "SQL"]

    result = extractor.extract(description, existing)

    assert result == ["python", "sql"]


def test_extract_handles_missing_description() -> None:
    extractor = SkillsExtractor(dictionary=_make_dictionary())

    result = extractor.extract(description=None, skills_raw=None)

    assert result == []


