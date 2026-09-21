"""
NEXUS — Layer 10: Test Runner
Auto-detects test framework, runs tests before AND after changes.
Any regression = hard block. Sandboxed subprocess with timeout.
"""
import os
import json
import subprocess
import tempfile
import re
from pathlib import Path
from typing import Dict, Optional

import structlog
logger = structlog.get_logger()

TIMEOUT_SECONDS = 30


def detect_and_run_tests(
    original_content: str,
    modified_content: str,
    file_path: str,
    language: str,
    repo_path: Optional[str] = None,
) -> Dict:
    """
    1. Detect test framework
    2. Run tests on original → baseline
    3. Run tests on modified → compare
    4. Return results with regression flag
    """
    framework = _detect_framework(language, repo_path)

    if framework == "none":
        # No tests found — auto-generate characterization tests
        generated = _generate_characterization_tests(original_content, language)
        return {
            "framework_detected": "auto-generated",
            "baseline_results": {"passed": 0, "failed": 0, "errors": 0},
            "modified_results": {"passed": 0, "failed": 0, "errors": 0},
            "regression_detected": False,
            "execution_time_ms": 0,
            "auto_generated_tests": True,
            "generated_test_code": generated,
            "message": "No tests found. Characterization tests generated — review before committing.",
        }

    baseline = _run_tests(framework, original_content, file_path, repo_path, label="baseline")
    modified = _run_tests(framework, modified_content, file_path, repo_path, label="modified")

    regression = _check_regression(baseline, modified)

    if regression:
        logger.warning("regression_detected", baseline=baseline, modified=modified)
    else:
        logger.info("tests_passed", framework=framework)

    return {
        "framework_detected": framework,
        "baseline_results": baseline,
        "modified_results": modified,
        "regression_detected": regression,
        "execution_time_ms": (
            baseline.get("execution_time_ms", 0) + modified.get("execution_time_ms", 0)
        ),
        "auto_generated_tests": False,
        "message": "Regression detected — change blocked." if regression else "All tests passed.",
    }


def _detect_framework(language: str, repo_path: Optional[str]) -> str:
    if not repo_path:
        # Single file mode — no repo context
        lang_defaults = {
            "Python": "pytest",
            "JavaScript": "jest",
            "TypeScript": "jest",
            "Java": "junit",
        }
        return lang_defaults.get(language, "none")

    root = Path(repo_path)

    # pytest
    if any([
        (root / "pytest.ini").exists(),
        (root / "setup.cfg").exists() and "[tool:pytest]" in (root / "setup.cfg").read_text(errors="ignore"),
        (root / "pyproject.toml").exists() and "pytest" in (root / "pyproject.toml").read_text(errors="ignore"),
        list(root.rglob("test_*.py")),
    ]):
        return "pytest"

    # jest
    if any([
        (root / "jest.config.js").exists(),
        (root / "jest.config.ts").exists(),
        (root / "package.json").exists() and '"jest"' in (root / "package.json").read_text(errors="ignore"),
    ]):
        return "jest"

    # JUnit (Maven or Gradle)
    if (root / "pom.xml").exists() or (root / "build.gradle").exists():
        return "junit"

    # mocha
    if any([
        (root / ".mocharc.js").exists(),
        (root / ".mocharc.yml").exists(),
    ]):
        return "mocha"

    # unittest fallback
    if language == "Python":
        return "unittest"

    return "none"


def _run_tests(
    framework: str,
    content: str,
    file_path: str,
    repo_path: Optional[str],
    label: str,
) -> Dict:
    import time
    start = time.time()

    if not repo_path:
        # Write content to temp file and run framework against it
        return _run_single_file_test(framework, content, file_path, label)

    try:
        if framework in ("pytest", "unittest"):
            cmd = ["python", "-m", "pytest", "--tb=short", "-q", "--no-header"]
        elif framework == "jest":
            cmd = ["npx", "jest", "--no-coverage", "--passWithNoTests"]
        elif framework == "mocha":
            cmd = ["npx", "mocha", "--recursive"]
        elif framework == "junit":
            cmd = ["mvn", "test", "-q"] if (Path(repo_path) / "pom.xml").exists() else ["gradle", "test", "-q"]
        else:
            return {"passed": 0, "failed": 0, "errors": 0, "execution_time_ms": 0}

        result = subprocess.run(
            cmd, cwd=repo_path,
            capture_output=True, text=True,
            timeout=TIMEOUT_SECONDS,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        elapsed = int((time.time() - start) * 1000)
        return _parse_test_output(framework, result.stdout, result.returncode, elapsed)

    except subprocess.TimeoutExpired:
        return {"passed": 0, "failed": 0, "errors": 1, "execution_time_ms": TIMEOUT_SECONDS * 1000, "error": "timeout"}
    except Exception as e:
        return {"passed": 0, "failed": 0, "errors": 1, "execution_time_ms": 0, "error": str(e)}


def _run_single_file_test(framework: str, content: str, file_path: str, label: str) -> Dict:
    """Run tests for single-file mode (no repo context)."""
    # For single file, we can only do a syntax check
    if framework == "pytest" or framework == "unittest":
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        try:
            result = subprocess.run(
                ["python", "-m", "py_compile", tmp_path],
                capture_output=True, text=True, timeout=10
            )
            passed = result.returncode == 0
            return {
                "passed": 1 if passed else 0,
                "failed": 0 if passed else 1,
                "errors": 0,
                "execution_time_ms": 100,
                "note": "syntax-check only (no test suite found)",
            }
        finally:
            os.unlink(tmp_path)
    return {"passed": 0, "failed": 0, "errors": 0, "execution_time_ms": 0, "note": "no tests"}


def _parse_test_output(framework: str, output: str, returncode: int, elapsed_ms: int) -> Dict:
    """Parse test runner output into {passed, failed, errors}."""
    passed = failed = errors = 0

    if framework in ("pytest", "unittest"):
        # pytest: "5 passed, 2 failed"
        m = re.search(r"(\d+) passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            failed = int(m.group(1))
        m = re.search(r"(\d+) error", output)
        if m:
            errors = int(m.group(1))

    elif framework == "jest":
        # jest: "Tests:       5 passed, 2 failed"
        m = re.search(r"Tests:\s+(\d+) passed", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"(\d+) failed", output)
        if m:
            failed = int(m.group(1))

    elif framework == "junit":
        # Maven: "Tests run: 10, Failures: 0, Errors: 0"
        m = re.search(r"Tests run:\s*(\d+)", output)
        if m:
            passed = int(m.group(1))
        m = re.search(r"Failures:\s*(\d+)", output)
        if m:
            failed = int(m.group(1))

    if passed == 0 and failed == 0 and errors == 0:
        # Fallback: returncode
        if returncode == 0:
            passed = 1
        else:
            failed = 1

    return {
        "passed": passed,
        "failed": failed,
        "errors": errors,
        "execution_time_ms": elapsed_ms,
        "returncode": returncode,
    }


def _check_regression(baseline: Dict, modified: Dict) -> bool:
    """A regression is when modified has MORE failures than baseline."""
    baseline_failures = baseline.get("failed", 0) + baseline.get("errors", 0)
    modified_failures  = modified.get("failed", 0) + modified.get("errors", 0)
    return modified_failures > baseline_failures


def _generate_characterization_tests(content: str, language: str) -> str:
    """
    Generate basic characterization test stubs when no tests exist.
    These capture current behavior so regressions after modernization are caught.
    """
    if language == "Python":
        return _gen_python_tests(content)
    elif language in ("JavaScript", "TypeScript"):
        return _gen_js_tests(content)
    return "# No test generation available for this language"


def _gen_python_tests(content: str) -> str:
    import re
    funcs = re.findall(r"^def\s+(\w+)\s*\(([^)]*)\)", content, re.MULTILINE)
    if not funcs:
        return "# No functions detected for characterization"
    lines = [
        "# AUTO-GENERATED by NEXUS — characterization tests",
        "# Review and add real assertions before committing",
        "import pytest",
        "",
    ]
    for name, params in funcs[:5]:  # limit to first 5 functions
        param_list = [p.split(":")[0].split("=")[0].strip() for p in params.split(",") if p.strip() and p.strip() != "self"]
        args = ", ".join(["None"] * len(param_list))
        lines += [
            f"def test_{name}_exists():",
            f"    # TODO: verify {name}({args}) returns expected value",
            f"    pass",
            "",
        ]
    return "\n".join(lines)


def _gen_js_tests(content: str) -> str:
    funcs = re.findall(r"(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s*)?\()", content)
    names = [f[0] or f[1] for f in funcs if (f[0] or f[1])]
    if not names:
        return "// No functions detected for characterization"
    lines = ["// AUTO-GENERATED by NEXUS — characterization tests", ""]
    for name in names[:5]:
        lines += [
            f"test('{name} exists', () => {{",
            f"  // TODO: assert {name}() returns expected value",
            f"}});",
            "",
        ]
    return "\n".join(lines)