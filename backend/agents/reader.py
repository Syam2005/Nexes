"""
NEXUS — Agent 1: Reader Agent
Dynamically identifies what "legacy" means for THIS language at THIS era.
Nothing hardcoded. Pure LLM reasoning from AST context.
Chunks large files at function boundaries.
"""
import json
import re
from typing import Dict, List, Optional

from groq import Groq
from core.config import settings
import structlog

logger = structlog.get_logger()

client = None

def _get_client():
    global client
    if client is None:
        client = Groq(api_key=settings.GROQ_API_KEY)
    return client


READER_SYSTEM_PROMPT = """You are a world-class senior software engineer specializing in codebase modernization.
Your job is to identify legacy patterns in code with extreme precision.

CRITICAL RULES:
1. You identify legacy patterns specific to the EXACT language version and era provided — not generic issues.
2. You ONLY report line numbers that actually exist in the code provided. Count carefully.
3. You focus on patterns that can be modernized safely and minimally.
4. You do NOT report style preferences — only genuine legacy/deprecated patterns.
5. You consider the cross-file dependency context provided — a function called from many places has higher impact.
6. You return ONLY valid JSON. No preamble, no markdown, no explanation outside JSON.

OUTPUT FORMAT (JSON array, nothing else):
[
  {
    "issue_type": "snake_case_identifier like print_statement or urllib2_usage",
    "description": "Why this is legacy — cite the specific version where it was deprecated",
    "affected_lines": [12, 34, 67],
    "priority": 1,
    "estimated_impact": "How many uses and what callers are affected",
    "modernization_hint": "What the modern equivalent is",
    "safe_to_auto_fix": true
  }
]

Priority: 1=breaking/deprecated, 2=important but works, 3=nice-to-have improvement
safe_to_auto_fix: false if the change could affect external callers or behavior"""


def analyze(
    content: str,
    language_info: Dict,
    ast_result: Dict,
    security_summary: Dict,
    file_path: str = "",
) -> List[Dict]:
    """
    Analyze code for legacy patterns.
    Automatically chunks files > 300 lines at function boundaries.
    Returns merged list of issues.
    """
    lines = content.splitlines()
    total_lines = len(lines)

    if total_lines <= settings.LLM_CHUNK_LINES:
        return _analyze_chunk(
            content, language_info, ast_result, security_summary, file_path
        )

    # Chunk at function boundaries
    logger.info("chunking_large_file", lines=total_lines, file=file_path)
    return _analyze_chunked(content, language_info, ast_result, security_summary, file_path)


def _analyze_chunked(
    content: str,
    language_info: Dict,
    ast_result: Dict,
    security_summary: Dict,
    file_path: str,
) -> List[Dict]:
    """Split file at function boundaries and analyze each chunk separately."""
    lines = content.splitlines()
    functions = ast_result.get("functions", [])
    all_issues = []
    seen_issues = set()

    if not functions:
        # No functions detected — chunk by line count
        chunk_size = settings.LLM_CHUNK_LINES
        for i in range(0, len(lines), chunk_size):
            chunk = "\n".join(lines[i:i + chunk_size])
            offset = i
            issues = _analyze_chunk(chunk, language_info, ast_result, security_summary, file_path, line_offset=offset)
            for issue in issues:
                key = (issue.get("issue_type"), tuple(issue.get("affected_lines", [])))
                if key not in seen_issues:
                    seen_issues.add(key)
                    all_issues.append(issue)
        return all_issues

    # Group functions into chunks of ~300 lines
    chunks = []
    current_lines = []
    current_start = 1

    for func in sorted(functions, key=lambda f: f["start_line"]):
        func_lines = lines[func["start_line"] - 1 : func["end_line"]]
        if len(current_lines) + len(func_lines) > settings.LLM_CHUNK_LINES and current_lines:
            chunks.append((current_start, "\n".join(current_lines)))
            current_lines = func_lines
            current_start = func["start_line"]
        else:
            current_lines.extend(func_lines)

    if current_lines:
        chunks.append((current_start, "\n".join(current_lines)))

    for start_line, chunk_content in chunks:
        issues = _analyze_chunk(
            chunk_content, language_info, ast_result, security_summary,
            file_path, line_offset=start_line - 1
        )
        for issue in issues:
            key = (issue.get("issue_type"), tuple(issue.get("affected_lines", [])))
            if key not in seen_issues:
                seen_issues.add(key)
                all_issues.append(issue)

    return all_issues


def _analyze_chunk(
    content: str,
    language_info: Dict,
    ast_result: Dict,
    security_summary: Dict,
    file_path: str,
    line_offset: int = 0,
) -> List[Dict]:
    """Send one chunk to the LLM for analysis."""
    language = language_info.get("language", "Unknown")
    era = language_info.get("era", "unknown")
    version_hint = language_info.get("version_hint", "")

    # Build compact AST summary (don't send full AST — too many tokens)
    func_summary = [
        {
            "name": f["name"],
            "lines": f"{f['start_line']}-{f['end_line']}",
            "callers": len(f.get("calls", [])),
            "is_public": f.get("is_public", True),
        }
        for f in ast_result.get("functions", [])[:20]  # cap at 20 funcs
    ]

    dep_graph = ast_result.get("dependency_graph", {})
    # Only show functions that are called by others (higher impact)
    cross_file_context = {
        k: v for k, v in dep_graph.items()
        if v  # only show non-empty call lists
    }

    security_brief = {
        "high_severity_count": security_summary.get("risk_summary", {}).get("high", 0),
        "issues_near_these_patterns": [
            f.get("issue") for f in security_summary.get("security_findings", [])[:3]
        ],
    }

    user_message = f"""Language: {language}
Era: {era}
Version hints: {version_hint}
File: {file_path}

AST Functions Summary:
{json.dumps(func_summary, indent=2)}

Cross-file dependency context (function → called by):
{json.dumps(cross_file_context, indent=2)}

Security findings already detected (do NOT re-report these as modernization issues):
{json.dumps(security_brief, indent=2)}

Code to analyze:
```
{content}
```

Identify ALL legacy patterns for {language} at era {era}.
Remember: affected_lines must be ACTUAL line numbers present in the code above.
{"Note: line numbers are offset by " + str(line_offset) + " from file start." if line_offset > 0 else ""}"""

    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            response = _get_client().chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": READER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,    # low temperature for precision
                max_tokens=2000,
                response_format={"type": "json_object"} if False else None,
            )
            raw = response.choices[0].message.content.strip()
            issues = _parse_json_response(raw)

            if issues is None:
                logger.warning("reader_json_parse_failed", attempt=attempt, raw=raw[:200])
                continue

            # Apply line offset for chunked files
            if line_offset > 0:
                for issue in issues:
                    issue["affected_lines"] = [
                        l + line_offset for l in issue.get("affected_lines", [])
                    ]

            logger.info("reader_agent_success", issues_found=len(issues), language=language, era=era)
            return issues

        except Exception as e:
            logger.error("reader_agent_error", attempt=attempt, error=str(e))
            if attempt == settings.LLM_MAX_RETRIES:
                return []

    return []


def _parse_json_response(raw: str) -> Optional[List[Dict]]:
    """Parse JSON from LLM response, handling common formatting issues."""
    # Strip markdown code blocks
    raw = re.sub(r"```(?:json)?", "", raw).strip()

    # Try direct parse first
    try:
        data = json.loads(raw)
        if isinstance(data, list):
            return data
        if isinstance(data, dict):
            # Sometimes LLM wraps in {"issues": [...]}
            for key in ("issues", "patterns", "results", "findings"):
                if key in data and isinstance(data[key], list):
                    return data[key]
    except json.JSONDecodeError:
        pass

    # Try to extract JSON array from response
    m = re.search(r"\[.*\]", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass

    return None
