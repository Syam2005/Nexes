"""
NEXUS — Layer 3: Security Scanner
Runs BEFORE modernization. Bandit + detect-secrets + Radon.
Security issues are REPORTED only — never auto-fixed.
HIGH severity = PR blocked.
"""
import json
import subprocess
import tempfile
import os
import re
from pathlib import Path
from typing import Dict, List, Any

import structlog
logger = structlog.get_logger()


def scan_file(file_path: str, content: str, language: str) -> Dict:
    """
    Run all security tools and return consolidated findings.
    Returns:
    {
        security_findings, secrets_found,
        complexity_before, maintainability_index,
        security_gate_passed, risk_summary
    }
    """
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=Path(file_path).suffix,
        delete=False,
        encoding="utf-8",
    ) as tmp:
        tmp.write(content)
        tmp_path = tmp.name

    try:
        findings = []
        secrets = []
        complexity = {}
        maintainability = None

        if language == "Python":
            findings.extend(_run_bandit(tmp_path))
            secrets.extend(_run_detect_secrets(tmp_path))
            complexity = _run_radon_cc(tmp_path)
            maintainability = _run_radon_mi(tmp_path)
        else:
            # For non-Python: regex-based heuristic security scan
            findings.extend(_heuristic_scan(content, language))
            secrets.extend(_run_detect_secrets(tmp_path))

        high_count = sum(1 for f in findings if f.get("severity") == "HIGH")
        medium_count = sum(1 for f in findings if f.get("severity") == "MEDIUM")

        return {
            "security_findings": findings,
            "secrets_found": secrets,
            "complexity_before": complexity,
            "maintainability_index": maintainability,
            "security_gate_passed": high_count == 0 and len(secrets) == 0,
            "risk_summary": {
                "high": high_count,
                "medium": medium_count,
                "low": len(findings) - high_count - medium_count,
                "secrets": len(secrets),
            },
        }
    finally:
        os.unlink(tmp_path)


def _run_bandit(file_path: str) -> List[Dict]:
    """Bandit static analysis for Python security issues."""
    try:
        result = subprocess.run(
            ["bandit", "-r", file_path, "-f", "json", "-q"],
            capture_output=True, text=True, timeout=30
        )
        if not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        findings = []
        for issue in data.get("results", []):
            findings.append({
                "tool": "bandit",
                "severity": issue.get("issue_severity", "LOW").upper(),
                "confidence": issue.get("issue_confidence", "LOW").upper(),
                "line": issue.get("line_number", 0),
                "issue": issue.get("issue_text", ""),
                "test_id": issue.get("test_id", ""),
                "cwe": issue.get("issue_cwe", {}).get("id", ""),
                "more_info": issue.get("more_info", ""),
            })
        return findings
    except FileNotFoundError:
        logger.warning("bandit_not_installed")
        return _heuristic_scan_python_security(_read_file(file_path))
    except Exception as e:
        logger.error("bandit_error", error=str(e))
        return []


def _run_detect_secrets(file_path: str) -> List[Dict]:
    """detect-secrets for hardcoded credentials."""
    try:
        result = subprocess.run(
            ["detect-secrets", "scan", file_path],
            capture_output=True, text=True, timeout=30
        )
        if not result.stdout.strip():
            return []
        data = json.loads(result.stdout)
        secrets = []
        for path, secret_list in data.get("results", {}).items():
            for s in secret_list:
                secrets.append({
                    "line": s.get("line_number", 0),
                    "type": s.get("type", "unknown"),
                    "verified": s.get("is_verified", False),
                })
        return secrets
    except FileNotFoundError:
        logger.warning("detect_secrets_not_installed")
        return _heuristic_secrets_scan(_read_file(file_path))
    except Exception as e:
        logger.error("detect_secrets_error", error=str(e))
        return []


def _run_radon_cc(file_path: str) -> Dict:
    """
    Radon cyclomatic complexity.

    FIX: Radon's JSON output is a dict keyed by filename, where each value is
    a LIST of result entries. Each entry is normally a dict describing a
    function/method/class — BUT Radon also emits non-dict entries in some
    versions/cases (e.g. a bare complexity-rank string, or an entry for a
    file-level parse error). The old code assumed every entry was a dict and
    called `.get()` on it unconditionally, which threw
    "'str' object has no attribute 'get'" whenever a non-dict entry appeared.
    Also dropped the `-s` (show rank) flag since it isn't used downstream and
    isn't needed for the plain complexity number.
    """
    try:
        result = subprocess.run(
            ["radon", "cc", file_path, "-j"],
            capture_output=True, text=True, timeout=30
        )
        if not result.stdout.strip():
            return {}
        data = json.loads(result.stdout)

        complexities = []
        for file_results in data.values():
            # file_results should be a list; guard in case Radon returns
            # something else (e.g. an error string) for this file.
            if not isinstance(file_results, list):
                continue
            for func in file_results:
                # Only process dict entries — skip strings/other types
                # that Radon sometimes includes (e.g. rank markers).
                if not isinstance(func, dict):
                    continue
                complexity_val = func.get("complexity")
                if isinstance(complexity_val, (int, float)):
                    complexities.append(complexity_val)

        if not complexities:
            return {}

        avg = sum(complexities) / len(complexities)
        return {
            "avg_cyclomatic": round(avg, 2),
            "max_cyclomatic": max(complexities),
            "functions_analyzed": len(complexities),
        }
    except FileNotFoundError:
        logger.warning("radon_not_installed")
        return {}
    except Exception as e:
        logger.warning("radon_cc_unavailable", error=str(e))
        return {}


def _run_radon_mi(file_path: str) -> float | None:
    """Radon maintainability index."""
    try:
        result = subprocess.run(
            ["radon", "mi", file_path, "-j"],
            capture_output=True, text=True, timeout=30
        )
        if not result.stdout.strip():
            return None
        data = json.loads(result.stdout)
        for v in data.values():
            if isinstance(v, dict):
                return round(v.get("mi", 0), 2)
    except Exception as e:
        logger.warning("radon_mi_unavailable", error=str(e))
    return None


def _heuristic_scan(content: str, language: str) -> List[Dict]:
    """Generic security heuristics for non-Python languages."""
    findings = []
    lines = content.splitlines()

    patterns = [
        # Hardcoded credentials
        (r'password\s*=\s*["\'][^"\']{4,}["\']',  "HIGH",   "Possible hardcoded password"),
        (r'api_key\s*=\s*["\'][^"\']{8,}["\']',   "HIGH",   "Possible hardcoded API key"),
        (r'secret\s*=\s*["\'][^"\']{8,}["\']',    "HIGH",   "Possible hardcoded secret"),
        # SQL injection
        (r'["\']\s*\+\s*\w+\s*\+\s*["\'].*SELECT', "HIGH",  "Possible SQL injection via concatenation"),
        (r'execute\s*\(\s*["\'][^"\']*["\'\s]\s*\+', "HIGH", "Possible SQL injection"),
        # XSS
        (r'innerHTML\s*=',                          "MEDIUM", "Possible XSS via innerHTML"),
        (r'document\.write\s*\(',                   "MEDIUM", "Possible XSS via document.write"),
        # Command injection
        (r'exec\s*\(\s*["\'].*\$',                  "HIGH",  "Possible command injection"),
        (r'eval\s*\(',                               "HIGH",  "Use of eval() — potential code injection"),
        # Weak crypto
        (r'\bmd5\b|\bsha1\b',                        "MEDIUM","Weak hashing algorithm"),
        # Insecure protocols
        (r'http://',                                 "LOW",   "Insecure HTTP — consider HTTPS"),
    ]

    for i, line in enumerate(lines, 1):
        for pattern, severity, issue in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "tool": "heuristic",
                    "severity": severity,
                    "confidence": "MEDIUM",
                    "line": i,
                    "issue": issue,
                    "test_id": "heuristic",
                    "cwe": "",
                })
    return findings


def _heuristic_scan_python_security(content: str) -> List[Dict]:
    """Python-specific heuristics when bandit unavailable."""
    findings = []
    lines = content.splitlines()
    patterns = [
        (r'\beval\s*\(',                             "HIGH",  "Use of eval()"),
        (r'\bexec\s*\(',                             "HIGH",  "Use of exec()"),
        (r'subprocess.*shell\s*=\s*True',            "HIGH",  "subprocess with shell=True"),
        (r'pickle\.load\b|yaml\.load\b',             "HIGH",  "Insecure deserialization"),
        (r'hashlib\.md5|hashlib\.sha1',              "MEDIUM","Weak hash algorithm"),
        (r'assert\s+',                               "LOW",   "Assert used for security check"),
        (r'%\s*\([^)]*\)\s*%\s*\w',                 "MEDIUM","String formatting in SQL-like context"),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, severity, issue in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                findings.append({
                    "tool": "heuristic_python",
                    "severity": severity,
                    "confidence": "MEDIUM",
                    "line": i,
                    "issue": issue,
                    "test_id": "heuristic",
                    "cwe": "",
                })
    return findings


def _heuristic_secrets_scan(content: str) -> List[Dict]:
    """Basic secret detection when detect-secrets unavailable."""
    secrets = []
    patterns = [
        r'[A-Z0-9]{20}[A-Z0-9/+]{20,}',  # AWS-style keys
        r'ghp_[a-zA-Z0-9]{36}',           # GitHub PAT
        r'sk-[a-zA-Z0-9]{32,}',           # OpenAI style
        r'(?i)password\s*[:=]\s*\S{8,}',  # Generic password
    ]
    for i, line in enumerate(content.splitlines(), 1):
        for pat in patterns:
            if re.search(pat, line):
                secrets.append({"line": i, "type": "possible_secret", "verified": False})
    return secrets


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except Exception:
        return ""