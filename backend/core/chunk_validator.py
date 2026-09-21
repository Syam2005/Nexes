"""
NEXUS — Layer 9: Chunk Validator
Re-parses the modified file with Tree-sitter after Diff Engine applies changes.
Catches syntax errors introduced by the LLM BEFORE tests run.
"""
from typing import Dict
from core.treesitter_parser import parse_file
TREE_SITTER_AVAILABLE = True
import structlog
logger = structlog.get_logger()


def validate_modified_file(
    language: str,
    original_content: str,
    modified_content: str,
    original_ast: Dict,
) -> Dict:
    """
    Validates the modified file:
    1. AST parses without errors
    2. All original function signatures still exist
    3. No unexpected new imports

    Returns: {ast_valid, signatures_preserved, unexpected_imports, validation_passed, issues}
    """
    if not TREE_SITTER_AVAILABLE:
        # Can't validate without tree-sitter — allow through with warning
        return {
            "ast_valid": True,
            "signatures_preserved": True,
            "unexpected_imports": [],
            "validation_passed": True,
            "issues": ["tree-sitter unavailable — validation skipped"],
        }

    # FIX: parse_file()'s real signature is
    #   parse_file(file_path, language_name, content=None, era=None)
    # The old call here was `parse_file(language, modified_content)`,
    # which passed `language` ("Python") into the file_path slot and the
    # actual source code into the language_name slot. Since the source
    # code string is never a key in TREE_SITTER_SUPPORTED, parse_file()
    # silently fell through to the LLM fallback path with a garbage
    # "file" (the 4-character language name) and a multi-hundred-line
    # string sitting in the file_path slot — producing an empty/garbage
    # AST with no functions detected. That's why every modernization run
    # reported "Functions removed from modified file: __init__,
    # validate_user, create_user" even when the actual modified file was
    # perfectly valid Python.
    #
    # We now pass a placeholder file_path (only used for extension-based
    # fallback hints and error messages, not for reading from disk, since
    # `content` is provided), the real language name, and the real
    # modified source.
    modified_ast = parse_file("modified_file.py", language.lower(), modified_content, None)
    issues = []

    # ── Check 1: AST is valid (no syntax errors) ──────────────────────────────
    ast_valid = modified_ast.get("ast_valid", False)
    if not ast_valid:
        issues.append("Modified file has syntax errors (AST parse failed)")

    # ── Check 2: Function signatures preserved ─────────────────────────────────
    original_funcs = {f["name"]: f for f in original_ast.get("functions", [])}
    modified_funcs = {f["name"]: f for f in modified_ast.get("functions", [])}
    missing_funcs = []

    for name, orig in original_funcs.items():
        if name not in modified_funcs:
            missing_funcs.append(name)
        else:
            mod = modified_funcs[name]
            # Check param count wasn't accidentally changed
            if len(orig.get("params", [])) != len(mod.get("params", [])):
                issues.append(
                    f"Function '{name}' param count changed: "
                    f"{len(orig['params'])} → {len(mod['params'])}"
                )

    signatures_preserved = len(missing_funcs) == 0
    if missing_funcs:
        issues.append(f"Functions removed from modified file: {', '.join(missing_funcs)}")

    # ── Check 3: No unexpected new imports ─────────────────────────────────────
    original_imports = {i["module"] for i in original_ast.get("imports", [])}
    modified_imports = {i["module"] for i in modified_ast.get("imports", [])}
    unexpected_imports = list(modified_imports - original_imports)

    # Some imports are expected (e.g. modernization adds 'requests' to replace 'urllib2')
    # We flag but don't fail on new imports — risk scorer handles this
    if unexpected_imports:
        issues.append(f"New imports detected: {', '.join(unexpected_imports)}")

    validation_passed = ast_valid and signatures_preserved

    if validation_passed:
        logger.info("chunk_validation_passed")
    else:
        logger.warning("chunk_validation_failed", issues=issues)

    return {
        "ast_valid": ast_valid,
        "signatures_preserved": signatures_preserved,
        "unexpected_imports": unexpected_imports,
        "validation_passed": validation_passed,
        "issues": issues,
        "modified_ast": modified_ast,
    }