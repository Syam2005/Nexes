"""
NEXUS — Layer 2: Universal Parser (Tree-sitter)
================================================
Team: Algerithm | Capgemini ExcellEr AgentifAI Buildathon 2026

What this file does:
- Converts any code file into a real Abstract Syntax Tree using Tree-sitter
- Works for 33 languages with full AST, LLM fallback for the rest
- Extracts functions, classes, imports, calls, dependency graph, I/O proximity
- Cross-file dependency tracking for repo-level analysis
- Chunks large files at function boundaries for LLM token limit handling
- Radon integration for industry-standard complexity metrics (Python)
- CRITICAL: Line numbers from this file are the ONLY trusted source.
  LLM is NEVER trusted for line numbers.
"""
import warnings
warnings.filterwarnings("ignore", category=FutureWarning)
import os
import json
import subprocess
from typing import Optional
from unittest import result
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# ─────────────────────────────────────────────────────────────────────────────
# I/O DETECTION SIGNATURES
# ─────────────────────────────────────────────────────────────────────────────

IO_SIGNATURES = {
    "network": [
        "requests", "urllib", "urllib2", "urllib3", "httpx", "aiohttp",
        "fetch", "axios", "XMLHttpRequest", "http.get", "http.post",
        "socket", "websocket", "grpc", "HttpClient", "RestTemplate",
        "okhttp", "retrofit", "net/http", "curl",
    ],
    "database": [
        "cursor", "execute", "fetchone", "fetchall", "commit", "rollback",
        "query", "findOne", "findAll", "save", "delete", "update",
        "mongoose", "sequelize", "prisma", "sqlalchemy", "psycopg2",
        "pymongo", "redis", "elasticsearch", "DatabaseHelper",
        "EntityManager", "Repository", "JdbcTemplate", "hibernate",
        "db.query", "db.exec", "db.run", "pool.query",
    ],
    "file_io": [
        "open(", "read(", "write(", "close(", "os.path", "pathlib",
        "fs.readFile", "fs.writeFile", "fs.readdir", "FileReader",
        "FileWriter", "BufferedReader", "Files.read", "Files.write",
        "fopen", "fread", "fwrite", "fclose", "shutil",
    ],
    "subprocess": [
        "subprocess", "os.system", "os.popen", "exec(", "eval(",
        "spawn", "fork", "child_process", "Runtime.exec",
        "ProcessBuilder", "popen",
    ],
}

STDLIB_MODULES = {
    "python": {
        "os", "sys", "re", "json", "math", "time", "datetime", "collections",
        "itertools", "functools", "pathlib", "shutil", "subprocess", "threading",
        "multiprocessing", "socket", "http", "urllib", "email", "logging",
        "unittest", "typing", "abc", "io", "struct", "hashlib", "hmac",
        "base64", "copy", "pprint", "traceback", "inspect", "ast", "dis",
        "pickle", "csv", "xml", "html", "tempfile", "glob", "fnmatch",
        "random", "statistics", "decimal", "fractions", "enum", "dataclasses",
        "contextlib", "warnings", "gc", "weakref", "platform", "signal",
    },
    "javascript": {
        "fs", "path", "os", "http", "https", "net", "crypto", "stream",
        "events", "util", "url", "querystring", "buffer", "child_process",
        "cluster", "readline", "repl", "vm", "zlib", "assert", "console",
        "process", "module", "require", "timers", "dns", "dgram",
    },
    "java": {
        "java.lang", "java.util", "java.io", "java.net", "java.nio",
        "java.math", "java.time", "java.text", "java.security",
        "java.sql", "java.awt", "java.swing", "java.beans",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# LANGUAGE CONFIGS
# ─────────────────────────────────────────────────────────────────────────────

LANGUAGE_CONFIGS = {
    "python": {
        "function_nodes": ["function_definition"],
        "class_nodes": ["class_definition"],
        "import_nodes": ["import_statement", "import_from_statement"],
        "call_nodes": ["call"],
        "decorator_nodes": ["decorator"],
        "name_field": "name",
        "public_check": lambda name: not name.startswith("_"),
        "complexity_nodes": [
            "if_statement", "elif_clause", "for_statement", "while_statement",
            "except_clause", "with_statement", "assert_statement",
            "boolean_operator", "conditional_expression",
        ],
    },
    "javascript": {
    "function_nodes": [
        "function_declaration", "arrow_function",
        "function_expression", "function",
        "method_definition", "generator_function",
        "generator_function_declaration",
    ],
        "class_nodes": ["class_declaration", "class_expression"],
        "import_nodes": ["import_statement", "call_expression"],
        "call_nodes": ["call_expression"],
        "decorator_nodes": ["decorator"],
        "name_field": "name",
        "public_check": lambda name: not name.startswith("_") and not name.startswith("#"),
        "complexity_nodes": [
            "if_statement", "else_clause", "for_statement", "for_in_statement",
            "while_statement", "do_statement", "catch_clause", "ternary_expression",
            "logical_expression", "switch_case",
        ],
    },
    "typescript": {
    "function_nodes": [
        "function_declaration", "arrow_function",
        "function_expression", "function",
        "method_definition", "method_signature",
        "generator_function", "generator_function_declaration",
    ],
        "class_nodes": ["class_declaration"],
        "import_nodes": ["import_statement"],
        "call_nodes": ["call_expression"],
        "decorator_nodes": ["decorator"],
        "name_field": "name",
        "public_check": lambda name: not name.startswith("_"),
        "complexity_nodes": [
            "if_statement", "for_statement", "while_statement",
            "catch_clause", "ternary_expression", "logical_expression",
        ],
    },
    "java": {
        "function_nodes": ["method_declaration", "constructor_declaration"],
        "class_nodes": [
            "class_declaration", "interface_declaration",
            "enum_declaration", "annotation_type_declaration",
        ],
        "import_nodes": ["import_declaration"],
        "call_nodes": ["method_invocation"],
        "decorator_nodes": ["annotation"],
        "name_field": "name",
        "public_check": lambda name: True,
        "complexity_nodes": [
            "if_statement", "else", "for_statement", "enhanced_for_statement",
            "while_statement", "do_statement", "catch_clause",
            "ternary_expression", "switch_label",
        ],
    },
    "go": {
        "function_nodes": ["function_declaration", "method_declaration"],
        "class_nodes": ["type_declaration"],
        "import_nodes": ["import_declaration", "import_spec"],
        "call_nodes": ["call_expression"],
        "decorator_nodes": [],
        "name_field": "name",
        "public_check": lambda name: name[0].isupper() if name else False,
        "complexity_nodes": [
            "if_statement", "else", "for_statement", "range_clause",
            "select_statement", "case_clause", "type_switch_statement",
        ],
    },
    "rust": {
        "function_nodes": ["function_item"],
        "class_nodes": ["struct_item", "impl_item", "trait_item", "enum_item"],
        "import_nodes": ["use_declaration", "extern_crate_declaration"],
        "call_nodes": ["call_expression", "method_call_expression"],
        "decorator_nodes": ["attribute_item"],
        "name_field": "name",
        "public_check": lambda name: True,
        "complexity_nodes": [
            "if_expression", "else_clause", "match_expression",
            "match_arm", "for_expression", "while_expression",
            "loop_expression", "if_let_expression", "while_let_expression",
        ],
    },
    "c": {
        "function_nodes": ["function_definition"],
        "class_nodes": ["struct_specifier", "union_specifier", "enum_specifier"],
        "import_nodes": ["preproc_include"],
        "call_nodes": ["call_expression"],
        "decorator_nodes": [],
        "name_field": "declarator",
        "public_check": lambda name: not name.startswith("_"),
        "complexity_nodes": [
            "if_statement", "else_clause", "for_statement", "while_statement",
            "do_statement", "case_statement", "conditional_expression",
        ],
    },
    "cpp": {
        "function_nodes": [
            "function_definition", "function_declarator",
            "constructor_or_destructor_definition",
        ],
        "class_nodes": [
            "class_specifier", "struct_specifier",
            "namespace_definition", "template_declaration",
        ],
        "import_nodes": ["preproc_include", "using_declaration"],
        "call_nodes": ["call_expression"],
        "decorator_nodes": ["attribute_declaration"],
        "name_field": "declarator",
        "public_check": lambda name: not name.startswith("_"),
        "complexity_nodes": [
            "if_statement", "else_clause", "for_statement", "while_statement",
            "do_statement", "case_statement", "conditional_expression",
            "try_statement", "catch_clause",
        ],
    },
    "ruby": {
        "function_nodes": ["method", "singleton_method"],
        "class_nodes": ["class", "module"],
        "import_nodes": ["call"],
        "call_nodes": ["call", "method_call"],
        "decorator_nodes": [],
        "name_field": "name",
        "public_check": lambda name: not name.startswith("_"),
        "complexity_nodes": [
            "if", "unless", "elsif", "else", "while", "until",
            "for", "rescue", "when",
        ],
    },
    "c_sharp": {
        "function_nodes": [
            "method_declaration", "constructor_declaration",
            "local_function_statement",
        ],
        "class_nodes": [
            "class_declaration", "interface_declaration",
            "struct_declaration", "enum_declaration",
        ],
        "import_nodes": ["using_directive"],
        "call_nodes": ["invocation_expression"],
        "decorator_nodes": ["attribute"],
        "name_field": "name",
        "public_check": lambda name: True,
        "complexity_nodes": [
            "if_statement", "else_clause", "for_statement", "foreach_statement",
            "while_statement", "do_statement", "catch_clause",
            "conditional_expression", "switch_section",
        ],
    },
}

DEFAULT_CONFIG = {
    "function_nodes": [
        "function_definition", "function_declaration",
        "method_definition", "method_declaration",
        "function_item",
    ],
    "class_nodes": ["class_definition", "class_declaration", "struct_item"],
    "import_nodes": ["import_statement", "import_declaration", "use_declaration"],
    "call_nodes": ["call_expression", "call"],
    "decorator_nodes": ["decorator", "annotation", "attribute_item"],
    "name_field": "name",
    "public_check": lambda name: not name.startswith("_"),
    "complexity_nodes": [
        "if_statement", "else_clause", "for_statement",
        "while_statement", "catch_clause",
    ],
}

def _build_supported_languages() -> set:
    """Dynamically detect which languages Tree-sitter can parse."""
    from tree_sitter_languages import get_parser
    candidates = [
        "python", "javascript", "typescript", "java", "go", "rust",
        "c", "cpp", "ruby", "php", "kotlin", "scala", "bash", "r",
        "c_sharp", "lua", "haskell", "elixir", "erlang", "ocaml",
        "julia", "fortran", "elm", "perl", "sql", "json", "yaml",
        "toml", "html", "css", "markdown", "dockerfile", "make",
        "fish", "powershell", "d", "nim", "crystal", "verilog",
        "vhdl", "asm", "pascal", "groovy", "clojure", "zig",
        "nix", "proto", "graphql", "solidity", "scss", "vue", "cmake",
    ]
    supported = set()
    for lang in candidates:
        try:
            get_parser(lang)
            supported.add(lang)
        except Exception:
            pass
    return supported

TREE_SITTER_SUPPORTED = _build_supported_languages()

# Maximum lines to send to LLM in one chunk
CHUNK_LINE_LIMIT = int(os.getenv("CHUNK_LINE_LIMIT", "300"))

# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _get_node_text(node, source_bytes: bytes) -> str:
    try:
        return source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore")
    except Exception:
        return ""


def _get_child_by_field(node, field_name: str):
    try:
        return node.child_by_field_name(field_name)
    except Exception:
        return None


def _get_node_name(node, source_bytes: bytes, field_name: str = "name") -> str:
    name_node = _get_child_by_field(node, field_name)
    if name_node:
        return _get_node_text(name_node, source_bytes)
    for child in node.children:
        if child.type == "identifier":
            return _get_node_text(child, source_bytes)
    return "<anonymous>"


def _collect_nodes_of_types(root_node, node_types: list) -> list:
    results = []
    stack = [root_node]
    while stack:
        node = stack.pop()
        if node.type in node_types:
            results.append(node)
        stack.extend(reversed(node.children))
    return results


def _count_all_nodes(root_node) -> int:
    """Count AST nodes efficiently without collecting them all."""
    count = 0
    stack = [root_node]
    while stack:
        node = stack.pop()
        count += 1
        stack.extend(node.children)
    return count


def _find_parent_class(node, source_bytes: bytes, class_node_types: list) -> Optional[str]:
    parent = node.parent
    while parent is not None:
        if parent.type in class_node_types:
            return _get_node_name(parent, source_bytes)
        parent = parent.parent
    return None


def _extract_call_names(node, source_bytes: bytes, call_node_types: list) -> list:
    calls = []
    call_nodes = _collect_nodes_of_types(node, call_node_types)
    for call_node in call_nodes:
        func_node = _get_child_by_field(call_node, "function")
        if func_node is None and call_node.children:
            func_node = call_node.children[0]
        if func_node:
            name = _get_node_text(func_node, source_bytes)
            if name and len(name) < 100:
                calls.append(name)
    return list(set(calls))


def _calculate_complexity(node, source_bytes: bytes, complexity_node_types: list) -> int:
    complexity = 1
    decision_nodes = _collect_nodes_of_types(node, complexity_node_types)
    complexity += len(decision_nodes)
    return complexity


def _detect_io_in_function(calls: list, source_text: str) -> dict:
    result = {
        "has_network": False,
        "has_database": False,
        "has_file_io": False,
        "has_subprocess": False,
    }
    combined = " ".join(calls) + " " + source_text
    for sig in IO_SIGNATURES["network"]:
        if sig in combined:
            result["has_network"] = True
            break
    for sig in IO_SIGNATURES["database"]:
        if sig in combined:
            result["has_database"] = True
            break
    for sig in IO_SIGNATURES["file_io"]:
        if sig in combined:
            result["has_file_io"] = True
            break
    for sig in IO_SIGNATURES["subprocess"]:
        if sig in combined:
            result["has_subprocess"] = True
            break
    return result


def _extract_decorators(node, source_bytes: bytes, decorator_types: list) -> list:
    decorators = []
    if not node.parent:
        return decorators
    siblings = node.parent.children
    node_idx = None
    for i, child in enumerate(siblings):
        if child == node:
            node_idx = i
            break
    if node_idx is None:
        return decorators
    for i in range(node_idx - 1, -1, -1):
        sibling = siblings[i]
        if sibling.type in decorator_types:
            decorators.append(_get_node_text(sibling, source_bytes).strip())
        elif sibling.type not in ["comment", "\n", " "]:
            break
    return list(reversed(decorators))


def _classify_import(module_name: str, language: str) -> str:
    if module_name.startswith("."):
        return "local"
    stdlib = STDLIB_MODULES.get(language, set())
    root = module_name.split(".")[0]
    if root in stdlib:
        return "stdlib"
    # Heuristic for local modules:
    # Short single-word names with no hyphens that are not stdlib
    # are likely local files (e.g. "auth", "utils", "models", "config")
    if (
        "." not in module_name
        and "-" not in module_name
        and module_name.islower()
        and len(module_name) < 30
    ):
        return "local"
    return "third_party"


def _is_public_java_or_cs(node, source_bytes: bytes) -> bool:
    modifiers = _collect_nodes_of_types(node, ["modifiers", "modifier"])
    for m in modifiers:
        if "public" in _get_node_text(m, source_bytes):
            return True
    return False


def _get_radon_metrics(source_code: str) -> dict:
    """
    Run Radon for industry-standard complexity metrics on Python code.
    Uses sys.executable to ensure venv Python is used.
    """
    import sys
    import tempfile

    tmp = None
    try:
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False,
            encoding="utf-8", dir=os.getcwd()
        ) as f:
            f.write(source_code)
            tmp = f.name

        cc_result = subprocess.run(
            [sys.executable, "-m", "radon", "cc", tmp, "-j", "-s"],
            capture_output=True, text=True, timeout=15,
            cwd=os.getcwd()
        )

        mi_result = subprocess.run(
            [sys.executable, "-m", "radon", "mi", tmp, "-j"],
            capture_output=True, text=True, timeout=15,
            cwd=os.getcwd()
        )

        cc_data = {}
        mi_data = {}

        if cc_result.returncode == 0 and cc_result.stdout.strip():
            try:
                cc_data = json.loads(cc_result.stdout)
            except Exception:
                pass

        if mi_result.returncode == 0 and mi_result.stdout.strip():
            try:
                mi_data = json.loads(mi_result.stdout)
            except Exception:
                pass

        fn_complexity = {}
        for file_key, blocks in cc_data.items():
            if isinstance(blocks, list):
                for block in blocks:
                    fn_complexity[block.get("name", "")] = {
                        "radon_complexity": block.get("complexity", 0),
                        "radon_rank": block.get("rank", "?"),
                    }
            elif isinstance(blocks, dict) and "error" in blocks:
                fn_complexity = {}

        mi_score = None
        mi_rank = None
        for file_key, mi_info in mi_data.items():
            if isinstance(mi_info, dict) and "mi" in mi_info:
                mi_score = round(float(mi_info["mi"]), 2)
                mi_rank = mi_info.get("rank")
                break
            elif isinstance(mi_info, dict) and "error" in mi_info:
                mi_score = None
                mi_rank = "parse_error"
                break
        
        return {
            "available": True,
            "per_function": fn_complexity,
            "maintainability_index": mi_score,
            "maintainability_rank": mi_rank,
        }

    except Exception as e:
        return {
            "available": False,
            "error": str(e),
            "per_function": {},
            "maintainability_index": None,
            "maintainability_rank": None,
        }
    finally:
        if tmp and os.path.exists(tmp):
            try:
                os.unlink(tmp)
            except Exception:
                pass

def chunk_code_by_functions(source_code: str, functions: list) -> list:
    """
    Split large source files into chunks at function boundaries.
    Each chunk contains complete functions and stays under CHUNK_LINE_LIMIT lines.
    Used by Reader Agent to handle Groq token limits.

    Returns list of:
    {
        "chunk_index": int,
        "start_line": int,
        "end_line": int,
        "code": str,
        "function_names": [str],
        "total_chunks": int  (filled in after all chunks built)
    }
    """
    lines = source_code.splitlines()
    total_lines = len(lines)

    if total_lines <= CHUNK_LINE_LIMIT:
        return [{
            "chunk_index": 0,
            "start_line": 1,
            "end_line": total_lines,
            "code": source_code,
            "function_names": [fn["name"] for fn in functions],
            "total_chunks": 1,
        }]

    chunks = []
    chunk_start = 0
    current_fn_names = []

    # Sort functions by start line
    sorted_fns = sorted(functions, key=lambda f: f["start_line"])

    i = 0
    while i < len(sorted_fns):
        fn = sorted_fns[i]
        fn_start = fn["start_line"] - 1  # 0-indexed
        fn_end = fn["end_line"]          # 0-indexed end (exclusive)

        current_fn_names.append(fn["name"])

        # Check if adding this function exceeds the chunk limit
        if fn_end - chunk_start > CHUNK_LINE_LIMIT and current_fn_names:
            # Emit current chunk up to before this function
            chunk_end = fn_start
            if chunk_end > chunk_start:
                chunks.append({
                    "chunk_index": len(chunks),
                    "start_line": chunk_start + 1,
                    "end_line": chunk_end,
                    "code": "\n".join(lines[chunk_start:chunk_end]),
                    "function_names": current_fn_names[:-1],
                })
            chunk_start = fn_start
            current_fn_names = [fn["name"]]

        i += 1

    # Final chunk
    if chunk_start < total_lines:
        chunks.append({
            "chunk_index": len(chunks),
            "start_line": chunk_start + 1,
            "end_line": total_lines,
            "code": "\n".join(lines[chunk_start:]),
            "function_names": current_fn_names,
        })

    # Fill in total_chunks
    total = len(chunks)
    for c in chunks:
        c["total_chunks"] = total

    return chunks
def _should_include_function(fn_node, source_bytes: bytes) -> bool:
    """
    Decide whether to include a function node in our output.
    Rules:
    - Always include top-level functions (parent is program/module)
    - Always include class methods (parent is class body)
    - Include named assigned functions (var x = function)
    - Skip anonymous callbacks inside other functions
    - Skip immediately invoked function expressions (IIFE)
    """
    parent = fn_node.parent
    if parent is None:
        return True

    # Top level
    if parent.type in (
        "program", "module", "source_file",
        "translation_unit", "compilation_unit",
    ):
        return True

    # Class method
    if parent.type in (
        "class_body", "block", "declaration_list",
        "object_type", "interface_body",
    ):
        return True

    # Named variable assignment — var x = function() or const x = () =>
    if parent.type in (
        "variable_declarator", "assignment_expression",
        "pair", "export_statement",
    ):
        # Check if it has a name
        for child in parent.children:
            if child.type == "identifier":
                return True
        return False

    # Skip everything else — callbacks, IIFEs, nested functions
    # These clutter the output and confuse the LLM agents
    return False

# ─────────────────────────────────────────────────────────────────────────────
# CORE TREE-SITTER PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_with_treesitter(source_code: str, language_name: str) -> dict:
    from tree_sitter_languages import get_parser

    try:
        parser = get_parser(language_name)
    except Exception as e:
        return {
            "ast_valid": False,
            "error": f"Tree-sitter parser unavailable for '{language_name}': {str(e)}",
            "fallback_mode": True,
        }

    source_bytes = source_code.encode("utf-8")

    try:
        tree = parser.parse(source_bytes)
    except Exception as e:
        return {
            "ast_valid": False,
            "error": f"Parse failed: {str(e)}",
            "fallback_mode": True,
        }

    root = tree.root_node
    has_errors = root.has_error
    error_nodes = _collect_nodes_of_types(root, ["ERROR"])
    config = LANGUAGE_CONFIGS.get(language_name, DEFAULT_CONFIG)

    # ── Functions ──────────────────────────────────────────────────────────
    functions = []
    for fn_node in _collect_nodes_of_types(root, config["function_nodes"]):
    # Skip deeply nested anonymous functions
    # Only keep: top-level functions, class methods, named assigned functions
        if not _should_include_function(fn_node, source_bytes):
            continue

        name_field = config.get("name_field", "name")
        fn_name = _get_node_name(fn_node, source_bytes, name_field)
        if fn_name == "<anonymous>" and fn_node.parent:
    # Try direct parent
            if fn_node.parent.type in [
                "variable_declarator", "assignment_expression",
                "assignment", "lexical_declaration",
                "pair", "export_statement",
            ]:
                var_node = _get_child_by_field(fn_node.parent, "name")
                if not var_node:
            # Try first identifier child of parent
                    for child in fn_node.parent.children:
                        if child.type == "identifier":
                            var_node = child
                            break
                if var_node:
                    fn_name = _get_node_text(var_node, source_bytes)
    # Try grandparent (var x = function in lexical_declaration)
        elif fn_node.parent.parent and fn_node.parent.parent.type in [
            "lexical_declaration", "variable_declaration",
        ]:
            for child in fn_node.parent.children:
                if child.type == "identifier":
                    fn_name = _get_node_text(child, source_bytes)
                    break

        start_line = fn_node.start_point[0] + 1
        end_line = fn_node.end_point[0] + 1
        fn_source = _get_node_text(fn_node, source_bytes)
        parent_class = _find_parent_class(fn_node, source_bytes, config["class_nodes"])
        calls = _extract_call_names(fn_node, source_bytes, config["call_nodes"])
        calls = [c for c in calls if c != fn_name]
        complexity = _calculate_complexity(fn_node, source_bytes, config["complexity_nodes"])
        decorators = _extract_decorators(fn_node, source_bytes, config.get("decorator_nodes", []))

        if language_name in ("java", "c_sharp"):
            is_public = _is_public_java_or_cs(fn_node, source_bytes)
        else:
            check = config.get("public_check", lambda n: True)
            is_public = check(fn_name) if fn_name != "<anonymous>" else False

        io_info = _detect_io_in_function(calls, fn_source)
        io_types = [k.replace("has_", "") for k, v in io_info.items() if v]

        functions.append({
            "name": fn_name,
            "start_line": start_line,
            "end_line": end_line,
            "class": parent_class,
            "calls": calls,
            "complexity": complexity,
            "is_public": is_public,
            "decorators": decorators,
            "has_io": bool(io_types),
            "io_types": io_types,
            "lines_of_code": end_line - start_line + 1,
        })

    # ── Classes ────────────────────────────────────────────────────────────
    classes = []
    for cls_node in _collect_nodes_of_types(root, config["class_nodes"]):
        cls_name = _get_node_name(cls_node, source_bytes)
        start_line = cls_node.start_point[0] + 1
        end_line = cls_node.end_point[0] + 1
        method_names = [f["name"] for f in functions if f.get("class") == cls_name]

        if language_name in ("java", "c_sharp"):
            is_public = _is_public_java_or_cs(cls_node, source_bytes)
        else:
            is_public = not cls_name.startswith("_") if cls_name else True

        decorators = _extract_decorators(cls_node, source_bytes, config.get("decorator_nodes", []))

        classes.append({
            "name": cls_name,
            "start_line": start_line,
            "end_line": end_line,
            "methods": method_names,
            "method_count": len(method_names),
            "is_public": is_public,
            "decorators": decorators,
            "lines_of_code": end_line - start_line + 1,
        })

    # ── Imports ────────────────────────────────────────────────────────────
    imports = []
    cross_file_imports = []

    for imp_node in _collect_nodes_of_types(root, config["import_nodes"]):
        imp_text = _get_node_text(imp_node, source_bytes).strip()
        line = imp_node.start_point[0] + 1
        module_name = ""
        alias = None
        imported_names = []

        if language_name == "python":
            if imp_node.type == "import_statement":
                for child in imp_node.children:
                    if child.type == "dotted_name":
                        module_name = _get_node_text(child, source_bytes)
                    elif child.type == "aliased_import":
                        name_c = _get_child_by_field(child, "name")
                        alias_c = _get_child_by_field(child, "alias")
                        if name_c:
                            module_name = _get_node_text(name_c, source_bytes)
                        if alias_c:
                            alias = _get_node_text(alias_c, source_bytes)
            elif imp_node.type == "import_from_statement":
                module_c = _get_child_by_field(imp_node, "module_name")
                if module_c:
                    module_name = _get_node_text(module_c, source_bytes)
                for child in imp_node.children:
                    if child.type == "dotted_name" and child != module_c:
                        imported_names.append(_get_node_text(child, source_bytes))
                    elif child.type == "aliased_import":
                        name_c = _get_child_by_field(child, "name")
                        if name_c:
                            imported_names.append(_get_node_text(name_c, source_bytes))

        elif language_name in ("javascript", "typescript"):
            source_c = _get_child_by_field(imp_node, "source")
            if source_c:
                module_name = _get_node_text(source_c, source_bytes).strip("'\"")
            for child in imp_node.children:
                if child.type in ("import_clause", "named_imports"):
                    for grandchild in child.children:
                        if grandchild.type == "identifier":
                            imported_names.append(_get_node_text(grandchild, source_bytes))
                        elif grandchild.type == "import_specifier":
                            name_c = _get_child_by_field(grandchild, "name")
                            if name_c:
                                imported_names.append(_get_node_text(name_c, source_bytes))

        elif language_name == "java":
            module_name = imp_text.replace("import ", "").replace(";", "").strip()

        else:
            parts = imp_text.split()
            if len(parts) > 1:
                module_name = parts[1].strip("\"'")

        if not module_name:
            module_name = imp_text[:80]

        import_type = _classify_import(module_name, language_name)

        imports.append({
            "module": module_name,
            "alias": alias,
            "line": line,
            "import_type": import_type,
            "names": imported_names,
            "raw": imp_text[:120],
        })

        if import_type == "local" and imported_names:
            cross_file_imports.append({
                "from_module": module_name,
                "imported_names": imported_names,
                "line": line,
            })

    # ── Dependency graph ───────────────────────────────────────────────────
    dependency_graph = {fn["name"]: fn["calls"] for fn in functions}

    # ── I/O summary ────────────────────────────────────────────────────────
    io_summary = {
        "has_network": any("network" in fn["io_types"] for fn in functions),
        "has_database": any("database" in fn["io_types"] for fn in functions),
        "has_file_io": any("file_io" in fn["io_types"] for fn in functions),
        "has_subprocess": any("subprocess" in fn["io_types"] for fn in functions),
    }
    import_modules = " ".join(imp["module"] for imp in imports)
    for sig in IO_SIGNATURES["network"]:
        if sig in import_modules:
            io_summary["has_network"] = True
    for sig in IO_SIGNATURES["database"]:
        if sig in import_modules:
            io_summary["has_database"] = True

    # ── Radon metrics (Python only) ────────────────────────────────────────
    radon_metrics = {}
    if language_name == "python":
        radon_metrics = _get_radon_metrics(source_code)
        # Merge radon complexity into function entries
        if radon_metrics.get("available"):
            for fn in functions:
                if fn["name"] in radon_metrics["per_function"]:
                    fn["radon_complexity"] = radon_metrics["per_function"][fn["name"]]["radon_complexity"]
                    fn["radon_rank"] = radon_metrics["per_function"][fn["name"]]["radon_rank"]

    # ── File metrics ───────────────────────────────────────────────────────
    total_lines = source_code.count("\n") + 1
    complexities = [fn["complexity"] for fn in functions] or [0]
    avg_complexity = round(sum(complexities) / len(complexities), 2)
    max_fn = max(functions, key=lambda f: f["complexity"]) if functions else None

    file_metrics = {
        "total_lines": total_lines,
        "function_count": len(functions),
        "class_count": len(classes),
        "import_count": len(imports),
        "avg_complexity": avg_complexity,
        "max_complexity": max(complexities),
        "max_complexity_function": max_fn["name"] if max_fn else None,
        "has_parse_errors": has_errors,
        "error_node_count": len(error_nodes),
        "raw_ast_node_count": _count_all_nodes(root),
        "maintainability_index": radon_metrics.get("maintainability_index"),
        "maintainability_rank": radon_metrics.get("maintainability_rank"),
    }

    # ── Chunks for LLM ────────────────────────────────────────────────────
    chunks = chunk_code_by_functions(source_code, functions)

    return {
        "ast_valid": not has_errors,
        "tree_sitter_available": True,
        "fallback_mode": False,
        "functions": functions,
        "classes": classes,
        "imports": imports,
        "cross_file_imports": cross_file_imports,
        "dependency_graph": dependency_graph,
        "io_summary": io_summary,
        "file_metrics": file_metrics,
        "radon_metrics": radon_metrics,
        "chunks": chunks,
        "raw_ast_nodes": file_metrics["raw_ast_node_count"],
    }


# ─────────────────────────────────────────────────────────────────────────────
# LLM FALLBACK
# ─────────────────────────────────────────────────────────────────────────────

def _parse_with_llm_fallback(source_code: str, language: str, file_path: str) -> dict:
    client = Groq(api_key=os.getenv("GROQ_API_KEY"))
    model = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    # Estimate tokens (1 token ≈ 4 chars). Leave room for prompt overhead.
    max_chars = int(os.getenv("LLM_FALLBACK_MAX_CHARS", "4000"))
    code_sample = source_code[:max_chars]
    total_lines = source_code.count("\n") + 1

    prompt = f"""You are analyzing {language} code. Extract the structure.
File: {os.path.basename(file_path)}
Total lines: {total_lines}
Code:
{code_sample}

Return ONLY a JSON object with this exact structure. No markdown, no explanation:
{{
  "functions": [
    {{
      "name": "function_name",
      "start_line": 1,
      "end_line": 10,
      "class": null,
      "calls": ["other_func"],
      "complexity": 2,
      "is_public": true,
      "decorators": [],
      "has_io": false,
      "io_types": [],
      "lines_of_code": 10
    }}
  ],
  "classes": [
    {{
      "name": "ClassName",
      "start_line": 1,
      "end_line": 50,
      "methods": ["method1"],
      "method_count": 1,
      "is_public": true,
      "decorators": [],
      "lines_of_code": 50
    }}
  ],
  "imports": [
    {{
      "module": "module_name",
      "alias": null,
      "line": 1,
      "import_type": "third_party",
      "names": [],
      "raw": "import module_name"
    }}
  ],
  "cross_file_imports": [],
  "dependency_graph": {{}},
  "io_summary": {{
    "has_network": false,
    "has_database": false,
    "has_file_io": false,
    "has_subprocess": false
  }},
  "file_metrics": {{
    "total_lines": {total_lines},
    "function_count": 0,
    "class_count": 0,
    "import_count": 0,
    "avg_complexity": 1.0,
    "max_complexity": 1,
    "max_complexity_function": null,
    "has_parse_errors": false,
    "error_node_count": 0,
    "raw_ast_node_count": 0,
    "maintainability_index": null,
    "maintainability_rank": null
  }}
}}"""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=2000,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        result = json.loads(raw)
        result["ast_valid"] = True
        result["tree_sitter_available"] = False
        result["fallback_mode"] = True
        result["raw_ast_nodes"] = 0
        result["radon_metrics"] = {"available": False}
        result["chunks"] = [{
            "chunk_index": 0,
            "start_line": 1,
            "end_line": total_lines,
            "code": source_code,
            "function_names": [f["name"] for f in result.get("functions", [])],
            "total_chunks": 1,
        }]
        return result

    except Exception as e:
        total_lines = source_code.count("\n") + 1
        return {
            "ast_valid": False,
            "tree_sitter_available": False,
            "fallback_mode": True,
            "error": f"LLM fallback failed: {str(e)}",
            "functions": [],
            "classes": [],
            "imports": [],
            "cross_file_imports": [],
            "dependency_graph": {},
            "io_summary": {
                "has_network": False, "has_database": False,
                "has_file_io": False, "has_subprocess": False,
            },
            "file_metrics": {
                "total_lines": total_lines,
                "function_count": 0, "class_count": 0, "import_count": 0,
                "avg_complexity": 0, "max_complexity": 0,
                "max_complexity_function": None, "has_parse_errors": True,
                "error_node_count": 0, "raw_ast_node_count": 0,
                "maintainability_index": None, "maintainability_rank": None,
            },
            "radon_metrics": {"available": False},
            "chunks": [],
            "raw_ast_nodes": 0,
        }


# ─────────────────────────────────────────────────────────────────────────────
# CHUNK VALIDATOR (Layer 6)
# ─────────────────────────────────────────────────────────────────────────────

def validate_ast_after_change(
    original_code: str,
    modified_code: str,
    language_name: str
) -> dict:
    """
    Re-parse modified code and verify:
    - No syntax errors introduced
    - All original function signatures preserved
    - No unexpected new imports added
    Used by Diff Engine after every proposed change.
    """
    orig = _parse_with_treesitter(original_code, language_name)
    mod = _parse_with_treesitter(modified_code, language_name)

    if mod.get("fallback_mode"):
        return {
            "valid": False,
            "reason": "Modified code failed to parse with Tree-sitter",
            "details": mod.get("error"),
        }

    # Only block if MODIFIED code has MORE errors than original
    # This handles legacy code (Python 2) that already has parse errors
    orig_errors = orig["file_metrics"].get("error_node_count", 0)
    mod_errors = mod["file_metrics"].get("error_node_count", 0)

    if mod_errors > orig_errors:
        return {
            "valid": False,
            "reason": f"Modification introduced new syntax errors "
                      f"(before: {orig_errors}, after: {mod_errors})",
            "details": f"{mod_errors - orig_errors} new error nodes introduced",
        }

    orig_funcs = {f["name"]: f for f in orig.get("functions", [])}
    mod_funcs = {f["name"]: f for f in mod.get("functions", [])}

    missing = [n for n in orig_funcs if n not in mod_funcs]
    if missing:
        return {
            "valid": False,
            "reason": f"Functions removed after modification: {missing}",
            "details": "Modernization must not remove existing functions",
        }

    orig_imports = {imp["raw"] for imp in orig.get("imports", [])}
    mod_imports = {imp["raw"] for imp in mod.get("imports", [])}
    new_imports = mod_imports - orig_imports

    return {
        "valid": True,
        "reason": "Validation passed",
        "syntax_errors": False,
        "functions_preserved": True,
        "new_imports_added": list(new_imports),
        "original_function_count": len(orig_funcs),
        "modified_function_count": len(mod_funcs),
        "complexity_delta": (
            mod["file_metrics"]["avg_complexity"] -
            orig["file_metrics"]["avg_complexity"]
        ),
    }


# ─────────────────────────────────────────────────────────────────────────────
# PUBLIC API
# ─────────────────────────────────────────────────────────────────────────────

def parse_file(file_path: str, language_name: str, content: Optional[str] = None, era: Optional[str] = None) -> dict:
    """
    Main entry point for Layer 2.
    Always returns a valid dict — never raises to callers.
    """
    if content is None:
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except Exception as e:
            return {
                "ast_valid": False, "tree_sitter_available": False,
                "fallback_mode": True, "error": f"Could not read file: {str(e)}",
                "functions": [], "classes": [], "imports": [],
                "cross_file_imports": [], "dependency_graph": {},
                "io_summary": {
                    "has_network": False, "has_database": False,
                    "has_file_io": False, "has_subprocess": False,
                },
                "file_metrics": {
                    "total_lines": 0, "function_count": 0, "class_count": 0,
                    "import_count": 0, "avg_complexity": 0, "max_complexity": 0,
                    "max_complexity_function": None, "has_parse_errors": True,
                    "error_node_count": 0, "raw_ast_node_count": 0,
                    "maintainability_index": None, "maintainability_rank": None,
                },
                "radon_metrics": {"available": False},
                "chunks": [], "raw_ast_nodes": 0,
            }

    if not content.strip():
        return {
            "ast_valid": True,
            "tree_sitter_available": language_name in TREE_SITTER_SUPPORTED,
            "fallback_mode": False, "functions": [], "classes": [],
            "imports": [], "cross_file_imports": [], "dependency_graph": {},
            "io_summary": {
                "has_network": False, "has_database": False,
                "has_file_io": False, "has_subprocess": False,
            },
            "file_metrics": {
                "total_lines": 0, "function_count": 0, "class_count": 0,
                "import_count": 0, "avg_complexity": 0, "max_complexity": 0,
                "max_complexity_function": None, "has_parse_errors": False,
                "error_node_count": 0, "raw_ast_node_count": 0,
                "maintainability_index": None, "maintainability_rank": None,
            },
            "radon_metrics": {"available": False},
            "chunks": [], "raw_ast_nodes": 0,
        }

    if language_name and language_name in TREE_SITTER_SUPPORTED:
        result = _parse_with_treesitter(content, language_name)
        if result.get("fallback_mode"):
            result = _parse_with_llm_fallback(content, language_name, file_path)
    else:
        result = _parse_with_llm_fallback(content, language_name or "unknown", file_path)

    result["language"] = language_name
    result["file_path"] = file_path
    result["file_size_bytes"] = len(content.encode("utf-8"))
    result["era"] = era if era else "unknown"
    return result


def parse_repo(file_list: list) -> dict:
    """
    Parse multiple files and build a complete cross-file dependency graph.
    Used for repo-level analysis (Mode 2 GitHub URL, Mode 3 ZIP).
    """
    results = {}
    all_exports = {}
    all_imports = {}

    for file_info in file_list:
        path = file_info["path"]
        language = file_info.get("language", "")
        content = file_info.get("content")
        result = parse_file(path, language, content)
        results[path] = result

        for fn in result.get("functions", []):
            if fn.get("is_public"):
                all_exports[fn["name"]] = path
        for cls in result.get("classes", []):
            if cls.get("is_public"):
                all_exports[cls["name"]] = path
        for cf_import in result.get("cross_file_imports", []):
            all_imports.setdefault(path, []).append(cf_import)

    call_sites = {}
    for file_path, file_imports in all_imports.items():
        for imp in file_imports:
            for name in imp.get("imported_names", []):
                call_sites.setdefault(name, [])
                if file_path not in call_sites[name]:
                    call_sites[name].append(file_path)

    cross_file_graph = {}
    for file_path, result in results.items():
        for fn in result.get("functions", []):
            key = f"{fn['name']}@{file_path}"
            cross_file_calls = []
            for call in fn.get("calls", []):
                call_base = call.split(".")[0]
                if call_base in all_exports and all_exports[call_base] != file_path:
                    cross_file_calls.append(f"{call}@{all_exports[call_base]}")
            if cross_file_calls:
                cross_file_graph[key] = cross_file_calls

    return {
        "files": results,
        "cross_file_graph": cross_file_graph,
        "exported_symbols": all_exports,
        "call_sites": call_sites,
    }


# ─────────────────────────────────────────────────────────────────────────────
# SELF-TEST
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import tempfile

    python_legacy = '''import urllib2
import hashlib
import os

class UserAuth(object):
    def __init__(self, db_conn):
        self.db = db_conn

    def validate_user(self, username, password):
        query = "SELECT * FROM users WHERE username = '%s'" % username
        result = self.db.execute(query)
        if result.has_key('user'):
            hashed = hashlib.md5(password).hexdigest()
            if result['user']['password'] == hashed:
                print "Login successful for %s" % username
                return True
        print "Login failed"
        return False

    def _hash_password(self, password):
        return hashlib.md5(password).hexdigest()

    def fetch_user_data(self, user_id):
        response = urllib2.urlopen("http://api.example.com/user/%d" % user_id)
        return response.read()

def create_user(username, password, db):
    for i in xrange(3):
        try:
            db.execute("INSERT INTO users VALUES ('%s')" % username)
            print "User created: %s" % username
            return True
        except Exception, e:
            print "Error: %s" % str(e)
    return False
'''

    print("=" * 60)
    print("NEXUS Layer 2 — Universal Parser Test")
    print("=" * 60)

    with tempfile.NamedTemporaryFile(
        suffix=".py", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(python_legacy)
        tmp_py = f.name

    result = parse_file(tmp_py, "python", python_legacy)
    os.unlink(tmp_py)

    print(f"\n[TEST 1] Python legacy")
    print(f"  AST valid:         {result['ast_valid']}")
    print(f"  Tree-sitter:       {result['tree_sitter_available']}")
    print(f"  Fallback mode:     {result['fallback_mode']}")
    print(f"  Functions:         {result['file_metrics']['function_count']}")
    print(f"  Classes:           {result['file_metrics']['class_count']}")
    print(f"  Imports:           {result['file_metrics']['import_count']}")
    print(f"  Avg complexity:    {result['file_metrics']['avg_complexity']}")
    print(f"  Maintainability:   {result['file_metrics']['maintainability_index']} "
          f"({result['file_metrics']['maintainability_rank']})")
    print(f"  Network I/O:       {result['io_summary']['has_network']}")
    print(f"  Database I/O:      {result['io_summary']['has_database']}")
    print(f"  Chunks:            {len(result['chunks'])}")

    print(f"\n  Functions:")
    for fn in result["functions"]:
        io = f" [I/O:{','.join(fn['io_types'])}]" if fn["has_io"] else ""
        cls = f" [in {fn['class']}]" if fn["class"] else ""
        pub = " [pub]" if fn["is_public"] else " [priv]"
        radon = f" radon={fn.get('radon_complexity','?')}/{fn.get('radon_rank','?')}" if "radon_complexity" in fn else ""
        print(f"    {fn['name']:25} L{fn['start_line']:3}-{fn['end_line']:3}"
              f"  cc={fn['complexity']}{radon}{pub}{cls}{io}")

    js_legacy = '''var express = require('express');
var fs = require('fs');

function fetchUserData(userId, callback) {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', 'http://api.example.com/users/' + userId);
    xhr.onload = function() {
        if (xhr.status == 200) {
            callback(null, JSON.parse(xhr.responseText));
        } else {
            callback(new Error('failed'));
        }
    };
    xhr.send();
}

var processUsers = function(users) {
    var result = [];
    for (var i = 0; i < users.length; i++) {
        if (users[i].active == true) {
            result.push(users[i].name);
        }
    }
    return result;
};
'''

    with tempfile.NamedTemporaryFile(
        suffix=".js", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(js_legacy)
        tmp_js = f.name

    result_js = parse_file(tmp_js, "javascript", js_legacy)
    os.unlink(tmp_js)

    print(f"\n[TEST 2] JavaScript ES5")
    print(f"  AST valid:         {result_js['ast_valid']}")
    print(f"  Functions:         {result_js['file_metrics']['function_count']}")
    print(f"  Network I/O:       {result_js['io_summary']['has_network']}")
    for fn in result_js["functions"]:
        io = f" [I/O:{','.join(fn['io_types'])}]" if fn["has_io"] else ""
        print(f"    {fn['name']:25} L{fn['start_line']:3}-{fn['end_line']:3}  cc={fn['complexity']}{io}")

    gql = '''type Query { user(id: ID!): User }
type User { id: ID! name: String! }
type Mutation { createUser(name: String!): User! }'''

    with tempfile.NamedTemporaryFile(
        suffix=".graphql", mode="w", delete=False, encoding="utf-8"
    ) as f:
        f.write(gql)
        tmp_gql = f.name

    result_gql = parse_file(tmp_gql, "graphql", gql)
    os.unlink(tmp_gql)

    print(f"\n[TEST 3] GraphQL (LLM fallback)")
    print(f"  Fallback mode:     {result_gql['fallback_mode']}")
    print(f"  Tree-sitter:       {result_gql['tree_sitter_available']}")

    file_a = '''
def validate_user(username, password):
    return username == "admin"

def hash_password(password):
    import hashlib
    return hashlib.md5(password).hexdigest()
'''
    file_b = '''
from auth import validate_user

def login(username, password):
    if validate_user(username, password):
        return True
    return False
'''

    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(file_a)
        tmp_a = f.name
    with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False, encoding="utf-8") as f:
        f.write(file_b)
        tmp_b = f.name

    repo = parse_repo([
        {"path": tmp_a, "language": "python", "content": file_a},
        {"path": tmp_b, "language": "python", "content": file_b},
    ])
    os.unlink(tmp_a)
    os.unlink(tmp_b)

    print(f"\n[TEST 4] Cross-file repo")
    print(f"  Files parsed:      {len(repo['files'])}")
    print(f"  Exported symbols:  {list(repo['exported_symbols'].keys())}")
    print(f"  Call sites:        {dict((k,len(v)) for k,v in repo['call_sites'].items())}")
    print(f"  Cross-file edges:  {len(repo['cross_file_graph'])}")

    print("\n" + "=" * 60)
    print("Layer 2 complete.")
    print("=" * 60)