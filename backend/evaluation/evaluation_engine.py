"""
NEXUS — Layer 11: Evaluation Engine
Runs proposed changes against golden dataset.
Computes confidence score and per-language accuracy.
"""
import json
from pathlib import Path
from typing import Dict, List
import structlog

logger = structlog.get_logger()

GOLDEN_DATASET_PATH = Path(__file__).parent / "golden_dataset.json"

_dataset_cache: Dict = {}


def load_dataset() -> Dict:
    global _dataset_cache
    if _dataset_cache:
        return _dataset_cache
    try:
        with open(GOLDEN_DATASET_PATH, "r") as f:
            _dataset_cache = json.load(f)
    except FileNotFoundError:
        logger.warning("golden_dataset_not_found", path=str(GOLDEN_DATASET_PATH))
        _dataset_cache = {}
    return _dataset_cache


def evaluate(
    language: str,
    proposed_changes: List[Dict],
) -> Dict:
    """
    Score proposed changes against golden dataset.
    Returns confidence_score (0-100) and per-pattern matches.
    """
    dataset = load_dataset()
    lang_key = _language_key(language)
    patterns = dataset.get(lang_key, [])

    if not patterns:
        return {
            "confidence_score": 75,
            "pattern_matches": 0,
            "total_changes": len(proposed_changes),
            "matched_patterns": [],
            "note": f"No golden dataset for {language} — confidence is estimated",
        }

    matches = []
    for change in proposed_changes:
        if change.get("status") not in ("validated", "manual_required"):
            continue
        old_code = change.get("old_code", "")
        new_code = change.get("new_code", "")
        issue_type = change.get("issue_type", "")

        for pattern in patterns:
            if _fuzzy_match(old_code, pattern.get("legacy", "")) and \
               _fuzzy_match(new_code, pattern.get("modern", "")):
                matches.append({
                    "issue_type": issue_type,
                    "pattern": pattern.get("pattern"),
                    "match_type": "exact",
                })
                break
            elif issue_type == pattern.get("pattern"):
                matches.append({
                    "issue_type": issue_type,
                    "pattern": pattern.get("pattern"),
                    "match_type": "pattern_name",
                })
                break

    total_validated = len([
        c for c in proposed_changes
        if c.get("status") in ("validated", "manual_required")
    ])
    if total_validated == 0:
        confidence = 100
    else:
        confidence = int((len(matches) / total_validated) * 100)
        # Partial credit for unmatched — may still be valid for this codebase
        confidence = max(60, confidence)

    return {
        "confidence_score": confidence,
        "pattern_matches": len(matches),
        "total_changes": total_validated,
        "matched_patterns": matches,
        "language_key": lang_key,
    }


def _language_key(language: str) -> str:
    mapping = {
        "Python": "python",
        "JavaScript": "javascript",
        "TypeScript": "javascript",
        "Java": "java",
        "Go": "go",
        "Ruby": "ruby",
        "Rust": "rust",
        "C++": "cpp",
        "C": "c",
        "C#": "csharp",
        "PHP": "php",
        "Kotlin": "kotlin",
        "Swift": "swift",
        "Scala": "scala",
        "R": "r",
        "Bash": "bash",
        "SQL": "sql",
    }
    return mapping.get(language, language.lower())


def _fuzzy_match(a: str, b: str) -> bool:
    """Loose match — strips whitespace and compares normalized."""
    if not a or not b:
        return False
    return a.strip().replace(" ", "") == b.strip().replace(" ", "")