"""
NEXUS — Layer 8: Diff Engine
Applies proposed changes, computes real unified diffs, calculates minimality score.
Rejects any change where old_code does not exist verbatim in the file,
and rejects any change where old_code is AMBIGUOUS (matches more than once),
since str.replace(..., 1) on an ambiguous match silently patches the wrong
location in the file — this was corrupting modernized output (functions
disappearing, syntax errors) even though individual diffs looked correct.
"""
import difflib
from typing import Dict, List, Any

import structlog
logger = structlog.get_logger()


def apply_changes(original_content: str, proposed_changes: List[Dict]) -> Dict:
    """
    Apply a list of proposed changes to the original file.
    Each change: {issue_type, old_code, new_code, line_start, line_end, reason}

    Returns:
    {
        original_file, modified_file, unified_diff,
        changes_applied, changes_rejected, minimality_score,
        lines_changed, total_lines, rejection_reasons
    }
    """
    modified = original_content
    applied = []
    rejected = []
    rejection_reasons = []

    # Sort by line number descending so later replacements don't shift earlier line numbers
    sorted_changes = sorted(proposed_changes, key=lambda c: c.get("line_start", 0), reverse=True)

    for change in sorted_changes:
        old_code = change.get("old_code", "")
        new_code = change.get("new_code", "")

        if not old_code:
            rejected.append(change)
            rejection_reasons.append({
                "issue_type": change.get("issue_type"),
                "reason": "old_code is empty",
            })
            continue

        # CRITICAL GUARD 1: old_code must exist verbatim
        occurrence_count = modified.count(old_code)
        if occurrence_count == 0:
            rejected.append(change)
            rejection_reasons.append({
                "issue_type": change.get("issue_type"),
                "reason": f"old_code not found verbatim in file: {repr(old_code[:60])}",
            })
            logger.warning(
                "change_rejected_not_found",
                issue_type=change.get("issue_type"),
                old_code_preview=old_code[:60],
            )
            continue

        # CRITICAL GUARD 2: old_code must be UNAMBIGUOUS (exactly one match).
        # str.replace(old_code, new_code, 1) always patches the FIRST
        # occurrence in the file. If old_code also appears elsewhere
        # (e.g. two near-identical print statements, or a short snippet
        # that's a substring of unrelated code), the replace can silently
        # land on the WRONG location, corrupting whatever follows it.
        # That was the root cause of "Functions removed from modified
        # file" / AST parse failures even though each diff looked fine
        # in isolation. We reject ambiguous changes instead of guessing.
        if occurrence_count > 1:
            # Try to disambiguate using line_start/line_end before giving up,
            # since the reader/modernizer agents already know which exact
            # line the change applies to.
            disambiguated = _try_disambiguate_by_line(
                modified, old_code, change.get("line_start"), change.get("line_end")
            )
            if disambiguated is None:
                rejected.append(change)
                rejection_reasons.append({
                    "issue_type": change.get("issue_type"),
                    "reason": (
                        f"old_code matches {occurrence_count} locations in file "
                        f"(ambiguous, could not disambiguate by line number): "
                        f"{repr(old_code[:60])}"
                    ),
                })
                logger.warning(
                    "change_rejected_ambiguous",
                    issue_type=change.get("issue_type"),
                    occurrence_count=occurrence_count,
                    old_code_preview=old_code[:60],
                )
                continue
            else:
                start_idx, end_idx = disambiguated
                modified = modified[:start_idx] + new_code + modified[end_idx:]
                applied.append(change)
                logger.info(
                    "change_applied",
                    issue_type=change.get("issue_type"),
                    disambiguated_by_line=True,
                )
                continue

        # Unambiguous — exactly one match. Safe to replace.
        modified = modified.replace(old_code, new_code, 1)
        applied.append(change)
        logger.info("change_applied", issue_type=change.get("issue_type"))

    # Compute unified diff
    original_lines = original_content.splitlines(keepends=True)
    modified_lines = modified.splitlines(keepends=True)
    diff_lines = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile="original",
        tofile="modernized",
        lineterm="",
    ))
    unified_diff = "".join(diff_lines)

    # Minimality score: % of file that was NOT changed
    total_lines = len(original_lines)
    changed_lines = sum(1 for line in diff_lines if line.startswith(("+", "-")) and not line.startswith(("+++", "---")))
    minimality = round(((total_lines - changed_lines / 2) / total_lines * 100), 2) if total_lines else 100.0
    minimality = max(0.0, min(100.0, minimality))

    if minimality < 80:
        logger.warning("low_minimality_score", score=minimality)

    return {
        "original_file":    original_content,
        "modified_file":    modified,
        "unified_diff":     unified_diff,
        "changes_applied":  len(applied),
        "changes_rejected": len(rejected),
        "rejected_changes": rejected,
        "rejection_reasons": rejection_reasons,
        "minimality_score": minimality,
        "lines_changed":    changed_lines // 2,
        "total_lines":      total_lines,
    }


def _try_disambiguate_by_line(content: str, old_code: str, line_start, line_end):
    """
    When old_code matches multiple locations in `content`, try to find the
    ONE match whose position corresponds to the change's declared
    line_start/line_end. Returns (start_char_idx, end_char_idx) for the
    correct match, or None if it can't be disambiguated safely.
    """
    if not line_start:
        return None

    lines = content.splitlines(keepends=True)
    # Build a map of line number -> character offset where that line begins
    offsets = []
    pos = 0
    for line in lines:
        offsets.append(pos)
        pos += len(line)
    offsets.append(pos)  # sentinel for end of file

    if line_start < 1 or line_start > len(lines):
        return None

    # Char offset where the target line starts (1-indexed line_start)
    target_start = offsets[line_start - 1]

    # Search window: allow the match to start anywhere on or after the
    # declared start line, within a small tolerance for prior changes
    # having already shifted things slightly in this same pass.
    search_from = target_start
    idx = content.find(old_code, search_from)

    if idx == -1:
        # old_code might start slightly before target_start due to
        # leading whitespace/indentation capture differences — fall back
        # to scanning all occurrences and picking the closest one to
        # target_start.
        all_occurrences = []
        start = 0
        while True:
            found = content.find(old_code, start)
            if found == -1:
                break
            all_occurrences.append(found)
            start = found + 1
        if not all_occurrences:
            return None
        idx = min(all_occurrences, key=lambda o: abs(o - target_start))

    return (idx, idx + len(old_code))


def compute_diff_only(original: str, modified: str) -> str:
    """Just compute the diff between two strings (used by chunk validator)."""
    return "".join(difflib.unified_diff(
        original.splitlines(keepends=True),
        modified.splitlines(keepends=True),
        fromfile="original",
        tofile="modernized",
        lineterm="",
    ))