"""
Seniority Level Extraction Utility

This module provides a shared function to extract seniority level from job
titles. It is used by multiple services (e.g. ranker, enricher) to keep
seniority logic consistent across the pipeline.

The extraction uses simple keyword and pattern matching on the job title to
determine whether a position is junior, intermediate, or senior level.
"""

import re

# Valid seniority levels (must match database CHECK constraints and marts schema)
VALID_SENIORITY_LEVELS = {"junior", "intermediate", "senior", "unknown"}


def extract_seniority_level(job_title: str) -> str:
    """
    Extract seniority level from a job title using keyword detection.

    This function analyzes the job title for common seniority indicators:
    - Junior: 'junior', 'jr', 'associate', 'entry', 'entry-level', Level I, 'intern'
    - Intermediate: 'intermediate', 'mid-level', 'mid level', 'mid', Level II
    - Senior: 'senior', 'sr'/'sr.', 'lead', 'principal', 'staff', 'architect',
              'chief', 'vp', 'vice president', 'director', 'manager', 'head of',
              'advanced', Level III

    Uses word boundaries for accurate matching to avoid false positives
    (e.g., "architect" won't match "architecture").

    Args:
        job_title: Job title string to analyze.

    Returns:
        Seniority level: 'junior', 'intermediate', 'senior', or 'unknown'.
        Returns 'unknown' if no seniority indicators are found or input is invalid.
    """
    if not job_title or not isinstance(job_title, str):
        return "unknown"

    job_title_lower = job_title.lower()

    # Check for Roman numeral levels first (I, II, III)
    # Level I = Junior, Level II = Intermediate, Level III = Senior
    # Check III first to avoid matching II or I within it
    # Patterns: "Engineer III", "Level III", "III", " iii ", etc.
    if (
        " iii" in job_title_lower
        or "level iii" in job_title_lower
        or job_title_lower.startswith("iii")
        or job_title_lower.endswith(" iii")
        or " iii," in job_title_lower
        or " iii)" in job_title_lower
        or " iii/" in job_title_lower
        or "engineer iii" in job_title_lower
        or " iii" in job_title_lower
    ):
        return "senior"

    # Patterns: "Engineer II", "Level II", "II", " ii ", etc.
    # Note: "Engineer II" has no space before II, so check for that pattern
    if (
        " ii " in job_title_lower
        or "level ii" in job_title_lower
        or job_title_lower.startswith("ii ")
        or job_title_lower.endswith(" ii")
        or " ii," in job_title_lower
        or " ii)" in job_title_lower
        or " ii/" in job_title_lower
        or "engineer ii" in job_title_lower
    ):
        return "intermediate"

    # Patterns: "Engineer I", "Level I", "I", " i ", etc.
    # Be careful with single "i" - only match if it's clearly a level indicator
    if (
        "level i" in job_title_lower
        or " i " in job_title_lower
        or job_title_lower.startswith("i ")
        or job_title_lower.endswith(" i")
        or " i," in job_title_lower
        or " i)" in job_title_lower
        or " i/" in job_title_lower
        or "engineer i " in job_title_lower
        or "engineer i)" in job_title_lower
    ):
        return "junior"

    # Check for numeric/letter levels (L4, L5, L6, etc.)
    # L4 = Intermediate, L5+ = Senior
    level_match = re.search(r"\bL([4-9]|[1-9][0-9]+)\b", job_title_lower)
    if level_match:
        level_num = int(level_match.group(1))
        if level_num >= 5:
            return "senior"
        if level_num == 4:
            return "intermediate"

    # Check for executive/leadership roles first (these are always senior)
    # Use word boundaries to avoid false matches (e.g., "architect" in "architecture")
    executive_patterns = [
        r"\bchief\b",  # Chief Data Engineering Officer
        r"\bvp\b",  # VP, Lead Data
        r"\bvice president\b",  # Vice President
        r"\bhead of\b",  # Head of Data
        r"\bdirector\b",  # Director
        r"\bmanager\b",  # Manager
        r"\badvanced\b",  # Advanced
    ]
    if any(re.search(pattern, job_title_lower) for pattern in executive_patterns):
        return "senior"

    if re.search(r"\bintern\b", job_title_lower):
        return "junior"

    # Seniority indicators - order matters (check more specific first)
    # We check 'senior' before 'intermediate' to catch "Senior Intermediate" correctly
    # Use word boundaries for more accurate matching
    seniority_keywords = {
        "senior": [
            r"\bsenior\b",  # Senior Data Engineer
            r"\bsr\.?\b",  # Sr. or Sr (with or without period)
            r"\blead\b",  # Lead Software Engineer
            r"\bprincipal\b",  # Principal Engineer
            r"\bstaff\b",  # Staff Engineer
            r"\barchitect\b",  # Architect
        ],
        "intermediate": [
            r"\bintermediate\b",
            r"\bmid-level\b",
            r"\bmid level\b",
            r"\bmid\b",
        ],
        "junior": [
            r"\bjunior\b",
            r"\bjr\.?\b",  # Jr. or Jr
            r"\bassociate\b",
            r"\bentry-level\b",
            r"\bentry level\b",
            r"\bentry\b",
        ],
    }

    # Determine job seniority - check in order of specificity
    for level, patterns in seniority_keywords.items():
        if any(re.search(pattern, job_title_lower) for pattern in patterns):
            return level

    # No seniority indicators found
    return "unknown"


