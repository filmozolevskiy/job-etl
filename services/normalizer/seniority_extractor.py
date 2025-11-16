"""
Seniority Level Extraction Utility

This module provides a shared function to extract seniority level from job titles.
Used by both the normalizer (to store seniority) and the ranker (for scoring).

The extraction uses simple keyword matching on the job title to determine
if a position is junior, intermediate, or senior level.
"""

import re

# Valid seniority levels (must match database CHECK constraints)
VALID_SENIORITY_LEVELS = {'junior', 'intermediate', 'senior', 'unknown'}


def extract_seniority_level(job_title: str) -> str:
    """
    Extract seniority level from a job title using keyword detection.

    This function analyzes the job title for common seniority indicators:
    - Junior: 'junior', 'jr', 'associate', 'entry', Level I
    - Intermediate: 'intermediate', 'mid-level', 'mid level', Level II
    - Senior: 'senior', 'sr', 'lead', 'principal', 'staff', 'architect', Level III

    Args:
        job_title: Job title string to analyze

    Returns:
        Seniority level: 'junior', 'intermediate', 'senior', or 'unknown'
        Returns 'unknown' if no seniority indicators are found

    Examples:
        >>> extract_seniority_level("Senior Data Engineer")
        'senior'
        >>> extract_seniority_level("Junior Software Developer")
        'junior'
        >>> extract_seniority_level("Mid-Level Analyst")
        'intermediate'
        >>> extract_seniority_level("Data Engineer")
        'unknown'
    """
    if not job_title or not isinstance(job_title, str):
        return 'unknown'

    job_title_lower = job_title.lower()

    # Check for Roman numeral levels first (I, II, III)
    # Level I = Junior, Level II = Intermediate, Level III = Senior
    # Check III first to avoid matching II or I within it
    # Patterns: "Engineer III", "Level III", "III", " iii ", etc.
    if (' iii' in job_title_lower or
        'level iii' in job_title_lower or
        job_title_lower.startswith('iii') or
        job_title_lower.endswith(' iii') or
        ' iii,' in job_title_lower or
        ' iii)' in job_title_lower or
        ' iii/' in job_title_lower or
        'engineer iii' in job_title_lower or
        ' iii' in job_title_lower):
        return 'senior'
    # Patterns: "Engineer II", "Level II", "II", " ii ", etc.
    # Note: "Engineer II" has no space before II, so check for that pattern
    if (' ii ' in job_title_lower or
        'level ii' in job_title_lower or
        job_title_lower.startswith('ii ') or
        job_title_lower.endswith(' ii') or
        ' ii,' in job_title_lower or
        ' ii)' in job_title_lower or
        ' ii/' in job_title_lower or
        'engineer ii' in job_title_lower):
        return 'intermediate'
    # Patterns: "Engineer I", "Level I", "I", " i ", etc.
    # Be careful with single "i" - only match if it's clearly a level indicator
    if ('level i' in job_title_lower or
        ' i ' in job_title_lower or
        job_title_lower.startswith('i ') or
        job_title_lower.endswith(' i') or
        ' i,' in job_title_lower or
        ' i)' in job_title_lower or
        ' i/' in job_title_lower or
        'engineer i ' in job_title_lower or
        'engineer i)' in job_title_lower):
        return 'junior'

    # Check for numeric/letter levels (L4, L5, L6, etc.)
    # L4 = Intermediate, L5+ = Senior
    level_match = re.search(r'\bL([4-9]|[1-9][0-9]+)\b', job_title_lower)
    if level_match:
        level_num = int(level_match.group(1))
        if level_num >= 5:
            return 'senior'
        elif level_num == 4:
            return 'intermediate'

    # Check for other seniority indicators
    if any(keyword in job_title_lower for keyword in ['advanced', 'director', 'manager', 'vp', 'vice president', 'head of']):
        return 'senior'

    if 'intern' in job_title_lower:
        return 'junior'

    # Seniority indicators - order matters (check more specific first)
    # We check 'senior' before 'intermediate' to catch "Senior Intermediate" correctly
    seniority_keywords = {
        'senior': ['senior', 'sr', 'lead', 'principal', 'staff', 'architect'],
        'intermediate': ['intermediate', 'mid-level', 'mid level', 'mid'],
        'junior': ['junior', 'jr', 'associate', 'entry', 'entry-level', 'entry level'],
    }

    # Determine job seniority - check in order of specificity
    for level, keywords in seniority_keywords.items():
        if any(keyword in job_title_lower for keyword in keywords):
            return level

    # No seniority indicators found
    return 'unknown'

