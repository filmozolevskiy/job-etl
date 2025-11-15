"""
Unit tests for the enricher service main workflow.
"""
from __future__ import annotations

from typing import Any
from collections.abc import Sequence

from services.enricher.main import run_enricher
from services.enricher.skills_extractor import SkillEntry, SkillsDictionary, SkillsExtractor


class StubEnricherDB:
    """In-memory stub of the database interface."""

    def __init__(self, rows: list[dict[str, Any]]):
        self.rows = rows
        self.persisted_updates: list[tuple[str, Sequence[str]]] = []

    def fetch_jobs_for_skills(
        self, *, only_missing: bool = True, **_: Any
    ) -> list[dict[str, Any]]:
        if only_missing:
            return [
                row for row in self.rows if not row.get("skills_raw")
            ]
        return list(self.rows)

    def update_job_skills_batch(
        self, updates: Sequence[tuple[str, Sequence[str]]]
    ) -> int:
        self.persisted_updates.extend(updates)
        return len(updates)


def _extractor() -> SkillsExtractor:
    dictionary = SkillsDictionary(
        [
            SkillEntry(name="python", aliases=("python", "python3")),
            SkillEntry(name="sql", aliases=("sql",)),
        ]
    )
    return SkillsExtractor(dictionary=dictionary)


def test_run_enricher_updates_changed_rows() -> None:
    """Test that enricher updates rows when extracted skills differ from existing."""
    db = StubEnricherDB(
        rows=[
            {
                "hash_key": "hash1",
                "description": "Looking for Python developers with SQL experience.",
                "skills_raw": ["Python"],
                "job_title": "Data Engineer",
                "company": "Acme",
            },
            {
                "hash_key": "hash2",
                "description": "Generalist role.",
                "skills_raw": [],
                "job_title": "Analyst",
                "company": "Globex",
            },
        ]
    )

    # Include existing rows so we can test updating hash1 from ["Python"] to ["python", "sql"]
    stats = run_enricher(db=db, extractor=_extractor(), include_existing=True)

    assert stats["fetched"] == 2
    assert stats["processed"] == 2
    assert stats["updated"] == 1
    assert stats["unchanged"] == 1
    assert db.persisted_updates == [("hash1", ["python", "sql"])]


def test_run_enricher_respects_dry_run() -> None:
    db = StubEnricherDB(
        rows=[
            {
                "hash_key": "hash3",
                "description": "Python and SQL.",
                "skills_raw": [],
                "job_title": "Engineer",
                "company": "Initech",
            },
        ]
    )

    stats = run_enricher(db=db, extractor=_extractor(), dry_run=True)

    assert stats["updated"] == 1
    assert db.persisted_updates == []


def test_run_enricher_include_existing_flag() -> None:
    """When include_existing is False, rows with skills are skipped."""
    db = StubEnricherDB(
        rows=[
            {
                "hash_key": "hash_existing",
                "description": "Python developer.",
                "skills_raw": ["python"],
                "job_title": "Developer",
                "company": "Initrode",
            },
        ]
    )

    # By default existing rows should not be refetched (updated=0).
    stats_no_existing = run_enricher(
        db=db,
        extractor=_extractor(),
        include_existing=False,
    )
    assert stats_no_existing["fetched"] == 0
    assert stats_no_existing["updated"] == 0

    # When include_existing=True the row is processed.
    db_with_existing = StubEnricherDB(rows=db.rows)
    stats_with_existing = run_enricher(
        db=db_with_existing,
        extractor=_extractor(),
        include_existing=True,
    )
    assert stats_with_existing["fetched"] == 1
    assert stats_with_existing["processed"] == 1

