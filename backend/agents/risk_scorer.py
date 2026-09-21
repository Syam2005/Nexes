"""
NEXUS — Agent 3: Risk Scorer
Uses REAL data — test results, diff size, caller count, I/O proximity, security findings.
LLM reasons from evidence. NOT a rule engine.
Returns per-change risk AND an overall repo modernization score.
"""
import json
import re
from typing import Dict, List, Optional

from groq import Groq
from core.config import settings
import structlog

logger = structlog.get_logger()

_client = None

def _get_client():
    global _client
    if _client is None:
        _client = Groq(api_key=settings.GROQ_API_KEY)
    return _client


RISK_SCORER_SYSTEM_PROMPT = """You are an expert software engineer specializing in risk assessment for code changes.

You receive REAL DATA about proposed code changes and must reason carefully about each change's risk.

RISK LEVELS:
- LOW: Pure syntax modernization, no behavioral change possible, tests pass, no external callers.
- MEDIUM: Behavioral change possible but tests pass, limited external callers, not near I/O.
- HIGH: Many external callers, near I/O/DB/network, tests uncertain, or security-adjacent change.

CRITICAL: Your risk assessment must be EVIDENCE-BASED. Cite specific numbers from the data provided.
Do not assign HIGH risk just to be safe — LOW risk changes that get blocked waste developer time.

Return ONLY valid JSON. No preamble, no explanation outside JSON.

OUTPUT FORMAT:
{
  "overall_risk": "LOW|MEDIUM|HIGH",
  "overall_score": 78,
  "modernization_readiness": "High — 8/10 changes are LOW risk and safe to apply immediately",
  "estimated_hours_saved": 3.5,
  "per_change_risk": [
    {
      "issue_type": "print_statement",
      "risk": "LOW",
      "confidence": 0.95,
      "reason": "Pure syntax change. 4 occurrences. Tests pass (12/12). No callers outside file.",
      "callers_affected": 0,
      "behavioral_change_possible": false,
      "recommended_action": "Apply immediately"
    }
  ],
  "risk_summary": {
    "low_count": 5,
    "medium_count": 2,
    "high_count": 1,
    "auto_applicable": 5
  }
}"""


def score_changes(
    changes: List[Dict],
    diff_result: Dict,
    test_result: Dict,
    ast_result: Dict,
    security_result: Dict,
    language_info: Dict,
) -> Dict:
    """Score risk for all proposed changes using real pipeline data."""
    if not changes:
        return {
            "overall_risk": "LOW",
            "overall_score": 100,
            "modernization_readiness": "No changes proposed",
            "estimated_hours_saved": 0,
            "per_change_risk": [],
            "risk_summary": {"low_count": 0, "medium_count": 0, "high_count": 0, "auto_applicable": 0},
        }

    # Build rich evidence package for LLM
    evidence = _build_evidence(changes, diff_result, test_result, ast_result, security_result)

    user_message = f"""Language: {language_info.get('language')} (era: {language_info.get('era')})

EVIDENCE PACKAGE:
{json.dumps(evidence, indent=2)}

Proposed changes to score:
{json.dumps([_summarize_change(c) for c in changes], indent=2)}

Score each change's risk based on the evidence above."""

    for attempt in range(settings.LLM_MAX_RETRIES + 1):
        try:
            response = _get_client().chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=[
                    {"role": "system", "content": RISK_SCORER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.1,
                max_tokens=2500,
            )
            raw = response.choices[0].message.content.strip()
            result = _parse_json_response(raw)

            if result is None:
                logger.warning("risk_scorer_parse_failed", attempt=attempt)
                continue

            # Compute estimated hours saved
            if "estimated_hours_saved" not in result:
                result["estimated_hours_saved"] = _estimate_hours_saved(changes)

            # Add overall repo modernization score (0-100)
            if "overall_score" not in result:
                result["overall_score"] = _compute_overall_score(result)

            logger.info("risk_scorer_success", overall_risk=result.get("overall_risk"))
            return result

        except Exception as e:
            logger.error("risk_scorer_error", attempt=attempt, error=str(e))

    # Fallback: rule-based scoring
    return _rule_based_fallback(changes, test_result, diff_result)


def _build_evidence(
    changes: List[Dict],
    diff_result: Dict,
    test_result: Dict,
    ast_result: Dict,
    security_result: Dict,
) -> Dict:
    """Build a rich evidence package from real pipeline data."""
    dep_graph = ast_result.get("dependency_graph", {})

    # Count callers for each function
    func_caller_counts = {}
    for caller, callees in dep_graph.items():
        for callee in callees:
            func_caller_counts[callee] = func_caller_counts.get(callee, 0) + 1

    # Identify I/O-adjacent patterns
    imports = [i["module"] for i in ast_result.get("imports", [])]
    io_imports = [m for m in imports if any(
        kw in m.lower() for kw in ["socket", "requests", "urllib", "http", "db", "sql", "redis", "mongo", "file", "open", "io"]
    )]

    return {
        "test_evidence": {
            "framework": test_result.get("framework_detected"),
            "baseline_passed": test_result.get("baseline_results", {}).get("passed", 0),
            "baseline_failed": test_result.get("baseline_results", {}).get("failed", 0),
            "modified_passed": test_result.get("modified_results", {}).get("passed", 0),
            "modified_failed": test_result.get("modified_results", {}).get("failed", 0),
            "regression_detected": test_result.get("regression_detected", False),
        },
        "diff_evidence": {
            "minimality_score": diff_result.get("minimality_score", 100),
            "lines_changed": diff_result.get("lines_changed", 0),
            "total_lines": diff_result.get("total_lines", 0),
            "changes_rejected": diff_result.get("changes_rejected", 0),
        },
        "dependency_evidence": {
            "function_caller_counts": func_caller_counts,
            "io_related_imports": io_imports,
            "cross_file_deps_count": len([v for v in dep_graph.values() if v]),
        },
        "security_evidence": {
            "high_severity_issues": security_result.get("risk_summary", {}).get("high", 0),
            "secrets_found": security_result.get("risk_summary", {}).get("secrets", 0),
            "security_gate_passed": security_result.get("security_gate_passed", True),
        },
        "complexity_evidence": {
            "avg_complexity_before": security_result.get("complexity_before", {}).get("avg_cyclomatic"),
            "maintainability_index": security_result.get("maintainability_index"),
        },
    }


def _summarize_change(change: Dict) -> Dict:
    """Compact summary of a change for LLM input."""
    return {
        "issue_type": change.get("issue_type"),
        "line_start": change.get("line_start"),
        "line_end": change.get("line_end"),
        "old_code_preview": (change.get("old_code") or "")[:80],
        "new_code_preview": (change.get("new_code") or "")[:80],
        "reason": change.get("reason", ""),
        "status": change.get("status", "validated"),
    }


def _estimate_hours_saved(changes: List[Dict]) -> float:
    """Estimate manual effort these changes would take."""
    # Rough estimates per change type
    time_map = {
        "print_statement": 0.1,
        "string_format_percent": 0.2,
        "urllib2_usage": 0.5,
        "has_key_removal": 0.1,
        "xrange_usage": 0.1,
        "var_declaration": 0.1,
        "arrow_function": 0.2,
        "promise_chain": 0.5,
        "raw_type": 0.3,
    }
    total = sum(
        time_map.get(c.get("issue_type", ""), 0.25)
        for c in changes
        if c.get("status") == "validated"
    )
    return round(total, 1)


def _compute_overall_score(result: Dict) -> int:
    """Compute 0-100 modernization readiness score."""
    summary = result.get("risk_summary", {})
    total = summary.get("low_count", 0) + summary.get("medium_count", 0) + summary.get("high_count", 0)
    if total == 0:
        return 100
    low = summary.get("low_count", 0)
    medium = summary.get("medium_count", 0)
    score = int(((low * 1.0 + medium * 0.5) / total) * 100)
    return min(100, max(0, score))


def _rule_based_fallback(
    changes: List[Dict],
    test_result: Dict,
    diff_result: Dict,
) -> Dict:
    """Fallback when LLM fails — simple rule-based scoring."""
    tests_pass = not test_result.get("regression_detected", False)
    minimality = diff_result.get("minimality_score", 100)

    per_change = []
    low = medium = high = 0

    safe_types = {"print_statement", "string_format_percent", "has_key_removal", "xrange_usage"}
    risky_types = {"urllib2_usage", "promise_chain", "class_inheritance"}

    for change in changes:
        itype = change.get("issue_type", "")
        if itype in safe_types and tests_pass:
            risk = "LOW"
            low += 1
        elif itype in risky_types or not tests_pass:
            risk = "HIGH"
            high += 1
        else:
            risk = "MEDIUM"
            medium += 1

        per_change.append({
            "issue_type": itype,
            "risk": risk,
            "confidence": 0.7,
            "reason": f"Rule-based assessment: {'safe pattern' if risk == 'LOW' else 'requires review'}",
            "callers_affected": 0,
            "behavioral_change_possible": risk != "LOW",
            "recommended_action": "Apply" if risk == "LOW" else "Review manually",
        })

    overall = "HIGH" if high > 0 else ("MEDIUM" if medium > 0 else "LOW")

    return {
        "overall_risk": overall,
        "overall_score": max(0, 100 - high * 30 - medium * 10),
        "modernization_readiness": f"{low} changes safe to apply immediately",
        "estimated_hours_saved": _estimate_hours_saved(changes),
        "per_change_risk": per_change,
        "risk_summary": {
            "low_count": low,
            "medium_count": medium,
            "high_count": high,
            "auto_applicable": low,
        },
    }


def _parse_json_response(raw: str) -> Optional[Dict]:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "overall_risk" in data:
            return data
    except json.JSONDecodeError:
        pass
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except Exception:
            pass
    return None
