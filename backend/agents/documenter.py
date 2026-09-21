"""
NEXUS — Agent 4: Documenter Agent
Writes complete PR-ready documentation and professional HTML email reports.
Receives everything from all pipeline layers and synthesizes into actionable reports.
"""
import json
import re
from datetime import datetime
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


DOCUMENTER_SYSTEM_PROMPT = """You are a senior engineering lead writing a professional code review report.

Write a complete, actionable modernization report. Be specific, concise, and professional.
Use real numbers from the data provided. Do not pad or repeat information.

The report will be posted as a GitHub PR comment and also emailed to the developer.
Write in clear technical English. No marketing language.

Return ONLY valid JSON with this exact structure:
{
  "executive_summary": "2-3 sentences: what was analyzed, what was found, recommendation",
  "security_section": "markdown string with security findings table",
  "modernization_section": "markdown string with proposed changes table",
  "quality_section": "markdown string: complexity before/after, maintainability score",
  "recommended_order": ["issue_type_1", "issue_type_2"],
  "pr_description": "ready-to-paste PR description string",
  "rollback_instructions": "exact git commands to undo NEXUS changes",
  "full_markdown": "the complete report as one markdown string"
}"""


def generate_report(
    language_info: Dict,
    security_result: Dict,
    issues: List[Dict],
    changes: List[Dict],
    diff_result: Dict,
    test_result: Dict,
    risk_result: Dict,
    validation_result: Dict,
    evaluation_result: Dict,
    source_name: str,
    analysis_id: str,
) -> Dict:
    """Generate complete documentation from all pipeline data."""

    evidence = {
        "source": source_name,
        "analysis_id": analysis_id,
        "language": language_info.get("language"),
        "era": language_info.get("era"),
        "timestamp": datetime.utcnow().isoformat(),
        "issues_found": len(issues),
        "changes_proposed": len([c for c in changes if c.get("status") == "validated"]),
        "changes_rejected": diff_result.get("changes_rejected", 0),
        "minimality_score": diff_result.get("minimality_score"),
        "lines_changed": diff_result.get("lines_changed"),
        "total_lines": diff_result.get("total_lines"),
        "security_high": security_result.get("risk_summary", {}).get("high", 0),
        "security_medium": security_result.get("risk_summary", {}).get("medium", 0),
        "secrets_found": len(security_result.get("secrets_found", [])),
        "security_gate_passed": security_result.get("security_gate_passed", True),
        "complexity_before": security_result.get("complexity_before", {}),
        "maintainability_index": security_result.get("maintainability_index"),
        "tests_framework": test_result.get("framework_detected"),
        "tests_passed": test_result.get("modified_results", {}).get("passed", 0),
        "tests_failed": test_result.get("modified_results", {}).get("failed", 0),
        "regression_detected": test_result.get("regression_detected", False),
        "overall_risk": risk_result.get("overall_risk"),
        "overall_score": risk_result.get("overall_score"),
        "estimated_hours_saved": risk_result.get("estimated_hours_saved"),
        "confidence_score": evaluation_result.get("confidence_score"),
        "ast_validated": validation_result.get("validation_passed"),
        "security_findings": security_result.get("security_findings", [])[:5],
        "secrets": security_result.get("secrets_found", []),
        "per_change_risk": risk_result.get("per_change_risk", []),
        "changes_summary": [
            {
                "issue_type": c.get("issue_type"),
                "risk": next(
                    (r.get("risk") for r in risk_result.get("per_change_risk", [])
                     if r.get("issue_type") == c.get("issue_type")),
                    "MEDIUM"
                ),
                "reason": c.get("reason"),
                "old_preview": (c.get("old_code") or "")[:60],
                "new_preview": (c.get("new_code") or "")[:60],
            }
            for c in changes if c.get("status") == "validated"
        ],
    }

    user_message = f"""Generate a complete modernization report for this analysis:

{json.dumps(evidence, indent=2)}

Write the full report. Include:
1. Executive summary (2-3 sentences, specific numbers)
2. Security findings (table format if any)
3. Proposed modernization changes (table: Issue | Old → New | Risk | Status)
4. Code quality metrics (before/after if available)
5. Recommended apply order (safest first)
6. PR description (ready to paste)
7. Rollback: git revert command for [NEXUS] commits"""

    try:
        response = _get_client().chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=[
                {"role": "system", "content": DOCUMENTER_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        raw = response.choices[0].message.content.strip()
        result = _parse_json_response(raw)

        if result:
            # Always ensure full_markdown is present
            if "full_markdown" not in result:
                result["full_markdown"] = _build_fallback_markdown(evidence)
            logger.info("documenter_success")
            return result

    except Exception as e:
        logger.error("documenter_error", error=str(e))

    # Fallback: build report from evidence directly
    return _build_fallback_report(evidence)


def _build_fallback_report(evidence: Dict) -> Dict:
    md = _build_fallback_markdown(evidence)
    return {
        "executive_summary": (
            f"Analyzed {evidence['source']} ({evidence['language']}, {evidence['era']} era). "
            f"Found {evidence['issues_found']} legacy issues, {evidence['changes_proposed']} changes proposed. "
            f"Overall risk: {evidence['overall_risk']}. "
            f"{'⚠️ Security issues found.' if not evidence['security_gate_passed'] else '✅ Security gate passed.'}"
        ),
        "security_section": _build_security_section(evidence),
        "modernization_section": _build_modernization_section(evidence),
        "quality_section": _build_quality_section(evidence),
        "recommended_order": [c["issue_type"] for c in evidence.get("changes_summary", [])],
        "pr_description": f"[NEXUS] Modernize {evidence['source']}: {evidence['changes_proposed']} changes",
        "rollback_instructions": "git log --oneline | grep '\\[NEXUS\\]'  # find NEXUS commits\ngit revert <commit-hash>  # revert specific commit",
        "full_markdown": md,
    }


def _build_fallback_markdown(e: Dict) -> str:
    lines = [
        f"# 🔧 NEXUS Modernization Report",
        f"**File:** `{e['source']}` | **Language:** {e['language']} ({e['era']}) | **Analysis:** `{e['analysis_id'][:8]}`",
        f"**Generated:** {e['timestamp'][:19].replace('T', ' ')} UTC",
        "",
        "---",
        "",
        "## Executive Summary",
        "",
        f"- **{e['issues_found']}** legacy patterns detected",
        f"- **{e['changes_proposed']}** changes proposed ({e['changes_rejected']} rejected)",
        f"- **Minimality score:** {e.get('minimality_score', 'N/A')}% of file unchanged",
        f"- **Overall risk:** {e.get('overall_risk', 'N/A')} | **Confidence:** {e.get('confidence_score', 'N/A')}%",
        f"- **Estimated time saved:** {e.get('estimated_hours_saved', 0)} hours",
        f"- **Tests:** {e.get('tests_passed', 0)} passed | Regression: {'⚠️ YES — changes blocked' if e.get('regression_detected') else '✅ None'}",
        "",
    ]

    # Security
    if not e.get("security_gate_passed", True) or e.get("security_high", 0) > 0:
        lines += [
            "## ⚠️ Security Issues",
            "",
            "> **SECURITY ISSUES FOUND — manual review required before modernization**",
            "",
            "| Tool | Severity | Line | Issue |",
            "|------|----------|------|-------|",
        ]
        for f in e.get("security_findings", []):
            lines.append(f"| {f.get('tool')} | **{f.get('severity')}** | {f.get('line')} | {f.get('issue')} |")
        lines.append("")

    # Changes
    if e.get("changes_summary"):
        lines += [
            "## Proposed Changes",
            "",
            "| Issue | Change | Risk | Action |",
            "|-------|--------|------|--------|",
        ]
        for c in e.get("changes_summary", []):
            lines.append(
                f"| `{c['issue_type']}` | `{c['old_preview']}` → `{c['new_preview']}` | "
                f"**{c['risk']}** | {c['reason']} |"
            )
        lines.append("")

    # Quality
    cc = e.get("complexity_before", {})
    if cc:
        lines += [
            "## Code Quality",
            "",
            f"- **Avg cyclomatic complexity:** {cc.get('avg_cyclomatic', 'N/A')}",
            f"- **Max cyclomatic complexity:** {cc.get('max_cyclomatic', 'N/A')}",
            f"- **Maintainability index:** {e.get('maintainability_index', 'N/A')}",
            "",
        ]

    # Rollback
    lines += [
        "## Rollback",
        "",
        "```bash",
        "# Find all NEXUS commits",
        "git log --oneline | grep '\\[NEXUS\\]'",
        "# Revert a specific NEXUS commit",
        "git revert <commit-hash>",
        "```",
    ]

    return "\n".join(lines)


def _build_security_section(e: Dict) -> str:
    if not e.get("security_findings") and not e.get("secrets"):
        return "✅ No security issues detected."
    rows = ["| Tool | Severity | Line | Issue |", "|------|----------|------|-------|"]
    for f in e.get("security_findings", []):
        rows.append(f"| {f.get('tool')} | {f.get('severity')} | {f.get('line')} | {f.get('issue')} |")
    return "\n".join(rows)


def _build_modernization_section(e: Dict) -> str:
    if not e.get("changes_summary"):
        return "No changes proposed."
    rows = ["| Issue | Risk | Description |", "|-------|------|-------------|"]
    for c in e.get("changes_summary", []):
        rows.append(f"| `{c['issue_type']}` | **{c['risk']}** | {c['reason']} |")
    return "\n".join(rows)


def _build_quality_section(e: Dict) -> str:
    cc = e.get("complexity_before", {})
    if not cc:
        return "Complexity metrics not available (Python only)."
    return (
        f"Avg complexity: {cc.get('avg_cyclomatic', 'N/A')} | "
        f"Max: {cc.get('max_cyclomatic', 'N/A')} | "
        f"Maintainability: {e.get('maintainability_index', 'N/A')}/100"
    )


def _parse_json_response(raw: str) -> Optional[Dict]:
    raw = re.sub(r"```(?:json)?", "", raw).strip()
    try:
        data = json.loads(raw)
        if isinstance(data, dict) and "executive_summary" in data:
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


def build_html_email(report: Dict, user_name: str, source_name: str, report_url: str = "#") -> str:
    """Build a professional HTML email from the report data.

    report_url should be the full frontend URL to the analysis page, e.g.
    https://nexus-2-7dg3.onrender.com/analysis/<analysis_id>
    Defaults to "#" for backward compatibility if not provided.
    """
    risk_color = {"LOW": "#22c55e", "MEDIUM": "#f59e0b", "HIGH": "#ef4444"}.get(
        report.get("overall_risk", "MEDIUM"), "#6b7280"
    )
    summary = report.get("executive_summary", "NEXUS analysis complete.")
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#0f172a;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#0f172a;padding:40px 20px">
  <tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="background:#1e293b;border-radius:12px;overflow:hidden">
      <!-- Header -->
      <tr><td style="background:linear-gradient(135deg,#6366f1,#8b5cf6);padding:32px 40px">
        <p style="margin:0;font-size:28px;font-weight:700;color:#fff;letter-spacing:-0.5px">⚡ NEXUS</p>
        <p style="margin:8px 0 0;font-size:14px;color:rgba(255,255,255,0.8)">Agentic Codebase Modernization</p>
      </td></tr>
      <!-- Body -->
      <tr><td style="padding:32px 40px">
        <p style="margin:0 0 8px;font-size:14px;color:#94a3b8">Hi {user_name},</p>
        <p style="margin:0 0 24px;font-size:16px;color:#e2e8f0">Your analysis of <strong style="color:#fff">{source_name}</strong> is complete.</p>
        <!-- Summary box -->
        <div style="background:#0f172a;border-radius:8px;padding:20px;margin-bottom:24px;border-left:4px solid {risk_color}">
          <p style="margin:0;font-size:14px;color:#94a3b8;line-height:1.6">{summary}</p>
        </div>
        <!-- CTA -->
        <div style="text-align:center;margin:32px 0">
          <a href="{report_url}" style="display:inline-block;background:#6366f1;color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;font-weight:600;font-size:15px">View Full Report →</a>
        </div>
        <!-- Footer -->
        <p style="margin:0;font-size:12px;color:#475569;text-align:center">NEXUS by Team Algerithm · Capgemini ExcellEr AgentifAI Buildathon 2026</p>
      </td></tr>
    </table>
  </td></tr>
</table>
</body></html>"""
