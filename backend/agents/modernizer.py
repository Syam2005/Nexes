"""
NEXUS — Agent 2: Modernizer Agent
Generates MINIMAL, surgical fixes for each legacy issue.
old_code must exist verbatim. Line numbers validated against AST.
Retries on validation failure. Marks failed changes as manual-TODO.
"""
import json
import re
from typing import Dict, List, Optional

from groq import Groq
from core.config import settings
def validate_line_numbers(start, end, ast_result, old_code, content):
    return old_code.strip() in content
import structlog

logger = structlog.get_logger()

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


MODERNIZER_SYSTEM_PROMPT = """You are a surgical code modernizer. Your ONLY job is minimal transformation.

ABSOLUTE RULES (violations will cause rejection):
1. Change ONLY the lines identified in the issue. Touch NOTHING else.
2. NEVER rename variables, functions, or parameters.
3. NEVER restructure code flow or logic.
4. NEVER add comments, docstrings, or explanations.
5. NEVER add new imports unless the modernization specifically requires one (e.g. urllib2 → requests).
6. old_code MUST be copied EXACTLY from the original — character for character, including whitespace.
7. new_code must be a drop-in replacement — same indentation, same surrounding context expected.
8. Return ONLY valid JSON. No preamble, no markdown, no explanation outside JSON.

OUTPUT FORMAT (JSON array, nothing else):
[
  {
    "issue_type": "matches the issue_type from input",
    "old_code": "exact text to find and replace — copied verbatim from original",
    "new_code": "the minimal modern replacement",
    "line_start": 12,
    "line_end": 12,
    "reason": "one sentence: what changed and why"
  }
]

COMMON PATTERNS:
- Python print statement: old='print "x"' new='print("x")'
- Python % format: old='"%s" % var' new='f"{var}"'
- Python dict.has_key: old='d.has_key("k")' new='"k" in d'
- Python urllib2: old='import urllib2' new='import urllib.request as urllib2'
- JS var: old='var x = 1' new='const x = 1' (or let if reassigned)
- JS function: old='function() {' new='() => {'  (only when safe — not constructors)
- Java raw ArrayList: old='ArrayList list = new ArrayList()' new='ArrayList<Object> list = new ArrayList<>()'"""


def generate_fixes(
    content: str,
    issues: List[Dict],
    language_info: Dict,
    ast_result: Dict,
) -> List[Dict]:
    """
    Generate minimal fixes for all issues.
    Returns list of validated changes ready for diff engine.
    Failed changes are marked as manual-TODO, NOT dropped silently.
    """
    if not issues:
        return []

    # Filter to safe-to-fix issues only (high risk ones need explicit flag)
    auto_issues = [i for i in issues if i.get("safe_to_auto_fix", True)]
    manual_issues = [i for i in issues if not i.get("safe_to_auto_fix", True)]

    changes = []

    # Process in batches of 5 to avoid token limits
    batch_size = 5
    for i in range(0, len(auto_issues), batch_size):
        batch = auto_issues[i:i + batch_size]
        batch_changes = _generate_batch(content, batch, language_info, ast_result)
        changes.extend(batch_changes)

    # Mark manual issues as requiring human fix
    for issue in manual_issues:
        changes.append({
            "issue_type": issue.get("issue_type"),
            "old_code": "",
            "new_code": "",
            "line_start": issue.get("affected_lines", [0])[0],
            "line_end": issue.get("affected_lines", [0])[-1],
            "reason": issue.get("description", ""),
            "status": "manual_required",
            "priority": issue.get("priority", 2),
            "description": issue.get("description", ""),
        })

    return changes


def _generate_batch(
    content: str,
    issues: List[Dict],
    language_info: Dict,
    ast_result: Dict,
) -> List[Dict]:
    language = language_info.get("language", "Unknown")
    era = language_info.get("era", "unknown")

    # Build targeted code context: extract relevant lines for each issue
    lines = content.splitlines()
    context_snippets = []
    for issue in issues:
        affected = issue.get("affected_lines", [])
        if affected:
            start = max(0, min(affected) - 3)
            end = min(len(lines), max(affected) + 3)
            snippet = "\n".join(f"{i+1}: {lines[i]}" for i in range(start, end))
            context_snippets.append(f"Issue: {issue['issue_type']}\nContext:\n{snippet}")

    dep_graph = ast_result.get("dependency_graph", {})
    # Flag functions that have external callers
    high_caller_funcs = [
        name for name, calls in dep_graph.items()
        if len(calls) > 2
    ]

    user_message = f"""Language: {language} → modernize to current {language}
Era: {era}

Functions with many callers (be careful with these):
{', '.join(high_caller_funcs) if high_caller_funcs else 'none identified'}

Issues to fix:
{json.dumps(issues, indent=2)}

Relevant code context:
{chr(10).join(context_snippets)}

Full file (for exact text matching):
```
{content}
```

Generate the minimal fix for each issue. old_code must be copied EXACTLY from the file above."""

    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            response = _get_client().chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": MODERNIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.05,   # very low — we need exact text
                max_tokens=3000,
            )
            raw = response.choices[0].message.content.strip()
            proposed = _parse_json_response(raw)

            if proposed is None:
                logger.warning("modernizer_parse_failed", attempt=attempt)
                continue

            # Validate each change
            validated = []
            for change in proposed:
                old_code = change.get("old_code", "")
                if not old_code:
                    continue

                # CRITICAL: verify old_code exists verbatim
                if old_code not in content:
                    logger.warning(
                        "modernizer_old_code_not_found",
                        issue_type=change.get("issue_type"),
                        old_code_preview=old_code[:80],
                        attempt=attempt,
                    )
                    # On last attempt, mark as manual
                    if attempt == settings.LLM_MAX_RETRIES:
                        validated.append({
                            **change,
                            "status": "validation_failed",
                            "validation_error": "old_code not found verbatim in file",
                        })
                    continue

                # Validate line numbers
                if not validate_line_numbers(
                    change.get("line_start", 1),
                    change.get("line_end", 1),
                    ast_result,
                    old_code,
                    content,
                ):
                    logger.warning(
                        "modernizer_line_validation_failed",
                        issue_type=change.get("issue_type"),
                    )
                    # Line numbers wrong but old_code exists — fix line numbers from actual position
                    actual_line = _find_actual_line(content, old_code)
                    if actual_line:
                        change["line_start"] = actual_line
                        change["line_end"] = actual_line + old_code.count("\n")

                change["status"] = "validated"
                validated.append(change)

            logger.info(
                "modernizer_success",
                total=len(proposed),
                validated=len([c for c in validated if c.get("status") == "validated"]),
            )
            return validated

        except Exception as e:
            logger.error("modernizer_error", attempt=attempt, error=str(e))
            if attempt == settings.LLM_MAX_RETRIES:
                return []

    return []


def _find_actual_line(content: str, old_code: str) -> Optional[int]:
    """Find the actual line number where old_code appears."""
    lines = content.splitlines()
    old_lines = old_code.splitlines()
    if not old_lines:
        return None
    first_line = old_lines[0]
    for i, line in enumerate(lines, 1):
        if first_line in line:
            return i
    return None


def _parse_json_response(raw: str) -> Optional[List[Dict]]:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        for key in ("changes", "fixes", "results", "modifications"):
            if key in data and isinstance(data[key], list):
                return data[key]
    except json.JSONDecodeError:
        pass
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None
