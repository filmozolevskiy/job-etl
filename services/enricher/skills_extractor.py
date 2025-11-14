"""
Skills extraction utilities driven by spaCy and keyword dictionaries.

The enricher service uses this module to derive a normalized list of skills
from free-text job descriptions and any provider supplied lists.  The
extracted skills are lower-cased, de-duplicated, and mapped to canonical
names defined in ``config/taxonomy/skills_dictionary.yml``.
"""
from __future__ import annotations

import logging
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import spacy
import yaml
from spacy.language import Language
from spacy.matcher import PhraseMatcher
from spacy.tokens import Doc

logger = logging.getLogger(__name__)

DEFAULT_DICTIONARY_RELATIVE_PATH = Path("config/taxonomy/skills_dictionary.yml")


@dataclass(frozen=True)
class SkillEntry:
    """Canonical skill definition with aliases used for matching."""

    name: str
    aliases: tuple[str, ...]


class SkillsDictionary:
    """Lookup helper that maps aliases back to canonical skill names."""

    def __init__(self, entries: Sequence[SkillEntry]):
        self._entries = entries
        alias_mapping: dict[str, str] = {}
        for entry in entries:
            alias_mapping[entry.name] = entry.name
            for alias in entry.aliases:
                alias_mapping[alias] = entry.name
        self._alias_to_canonical = alias_mapping

    def lookup(self, raw_value: Optional[str]) -> Optional[str]:
        """
        Map a raw string to the canonical skill name, if known.

        Args:
            raw_value: Free-text string representing a potential skill.

        Returns:
            Canonical skill name (lower case) when recognised, otherwise None.
        """
        if not raw_value:
            return None
        normalized = raw_value.strip().lower()
        if not normalized:
            return None
        return self._alias_to_canonical.get(normalized)

    @property
    def entries(self) -> Sequence[SkillEntry]:
        """Expose defined entries (useful for debugging and tests)."""
        return self._entries


def load_skills_dictionary(
    path: Optional[Path | str] = None,
) -> SkillsDictionary:
    """
    Load skills dictionary from YAML configuration.

    Args:
        path: Optional override for dictionary file path. When omitted the
            default ``config/taxonomy/skills_dictionary.yml`` is used.

    Returns:
        SkillsDictionary populated with canonical names and aliases.
    """
    resolved_path = Path(path) if path else DEFAULT_DICTIONARY_RELATIVE_PATH

    if not resolved_path.is_absolute():
        project_root = Path(__file__).parent.parent.parent
        resolved_path = (project_root / resolved_path).resolve()

    if not resolved_path.exists():
        logger.warning(
            "Skills dictionary file not found at %s; falling back to defaults",
            resolved_path,
        )
        return SkillsDictionary(default_skill_entries())

    with resolved_path.open("r", encoding="utf-8") as handle:
        try:
            loaded = yaml.safe_load(handle) or {}
        except yaml.YAMLError as exc:
            logger.error(
                "Failed to parse skills dictionary YAML: %s", exc, exc_info=True
            )
            return SkillsDictionary(default_skill_entries())

    skills_section = loaded.get("skills")
    if skills_section is None:
        # Support shorthand where canonical mapping is top-level.
        skills_section = loaded

    if not isinstance(skills_section, Mapping):
        logger.warning(
            "Unexpected skills dictionary structure; using defaults. Type=%s",
            type(skills_section).__name__,
        )
        return SkillsDictionary(default_skill_entries())

    entries: list[SkillEntry] = []
    for canonical, config in skills_section.items():
        if not isinstance(canonical, str):
            continue
        aliases: Iterable[str]
        if isinstance(config, Mapping):
            aliases = config.get("aliases", []) or []
        elif isinstance(config, Sequence) and not isinstance(config, str):
            aliases = config
        else:
            aliases = []

        cleaned_aliases = {
            alias.strip().lower()
            for alias in aliases
            if isinstance(alias, str) and alias.strip()
        }
        # Guarantee canonical itself is included as alias.
        cleaned_aliases.add(canonical.strip().lower())
        entries.append(
            SkillEntry(
                name=canonical.strip().lower(),
                aliases=tuple(sorted(cleaned_aliases)),
            )
        )

    if not entries:
        logger.warning("Skills dictionary contained no valid entries; using defaults")
        return SkillsDictionary(default_skill_entries())

    return SkillsDictionary(entries)


def default_skill_entries() -> list[SkillEntry]:
    """
    Fallback dictionary used when user configuration is missing.

    This keeps the extractor functional (particularly in tests) while clearly
    logging that the curated taxonomy should be provided.
    """
    defaults = {
        "python": ["python"],
        "sql": ["sql", "structured query language"],
        "airflow": ["airflow", "apache airflow"],
        "dbt": ["dbt", "data build tool"],
        "tableau": ["tableau"],
        "docker": ["docker"],
        "aws": ["aws", "amazon web services"],
        "spark": ["spark", "apache spark"],
        "pandas": ["pandas"],
        "machine learning": ["machine learning", "ml"],
    }
    result: list[SkillEntry] = []
    for canonical, aliases in defaults.items():
        values = {canonical}
        values.update(aliases)
        result.append(
            SkillEntry(name=canonical, aliases=tuple(sorted(values)))
        )
    return result


class SkillsExtractor:
    """
    Extracts canonical skills from job descriptions and raw provider lists.

    The extractor combines:
    - A curated alias dictionary for keyword matching (using spaCy phrase matcher)
    - Token-level scanning for individual keywords
    - Normalisation of provider supplied ``skills_raw`` arrays
    """

    def __init__(
        self,
        dictionary: Optional[SkillsDictionary] = None,
        nlp: Optional[Language] = None,
    ) -> None:
        """
        Initialise extractor with dictionary and spaCy language model.

        Args:
            dictionary: Optional pre-built dictionary. If omitted, the default
                YAML-backed dictionary is loaded.
            nlp: Optional spaCy language pipeline. A lightweight blank English
                pipeline is used by default to avoid large model downloads.
        """
        self.dictionary = dictionary or load_skills_dictionary()
        self.nlp = nlp or spacy.blank("en")
        self.matcher = PhraseMatcher(self.nlp.vocab, attr="LOWER")
        for entry in self.dictionary.entries:
            phrases = [
                self.nlp.make_doc(alias)
                for alias in entry.aliases
                if len(alias.split()) > 1
            ]
            if phrases:
                self.matcher.add(entry.name, phrases)

    def extract(
        self,
        description: Optional[str],
        skills_raw: Optional[Collection[str]] = None,
    ) -> list[str]:
        """
        Derive canonical skills for a single job posting.

        Args:
            description: Job description free text.
            skills_raw: Optional list of skills supplied by the provider.

        Returns:
            Sorted list of unique, lower-cased skills.
        """
        matched_skills: set[str] = set[str]()

        # Normalise provider supplied skills first.
        for raw in skills_raw or []:
            canonical = self.dictionary.lookup(raw)
            if canonical:
                matched_skills.add(canonical)
            else:
                cleaned = self._clean_freetext(raw)
                if cleaned:
                    matched_skills.add(cleaned)

        doc = self._make_doc(description)
        if doc is not None:
            matched_skills.update(self._match_phrases(doc))
            matched_skills.update(self._match_tokens(doc))

        return sorted(matched_skills)

    def _make_doc(self, text: Optional[str]) -> Optional[Doc]:
        if not text or not text.strip():
            return None
        try:
            return self.nlp(text)
        except Exception as exc:
            logger.error("spaCy pipeline failed to parse description: %s", exc)
            return None

    def _match_phrases(self, doc: Doc) -> set[str]:
        skills: set[str] = set()
        for match_id, _, _ in self.matcher(doc):
            canonical = self.nlp.vocab.strings[match_id]
            if canonical:
                skills.add(canonical)
        return skills

    def _match_tokens(self, doc: Doc) -> set[str]:
        skills: set[str] = set()
        for token in doc:
            if token.is_punct or token.is_space:
                continue
            text_value = token.text.strip().lower()
            if not text_value:
                continue
            canonical = self.dictionary.lookup(text_value)
            if canonical:
                skills.add(canonical)
        return skills

    @staticmethod
    def _clean_freetext(value: str) -> Optional[str]:
        cleaned = value.strip().lower()
        return cleaned or None

