"""
Enricher service package.

This package contains the enrichment logic responsible for augmenting
normalized job postings with derived attributes such as extracted skills.
"""

from .skills_extractor import SkillsExtractor, load_skills_dictionary

__all__ = [
    "SkillsExtractor",
    "load_skills_dictionary",
]

