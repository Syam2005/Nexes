"""
NEXUS — Layer 1: Language Detector
Identifies language AND era from file extension + content signatures.
Never returns just "Python" — returns "Python 2.7 era" with version hints.
"""
import re
from pathlib import Path
from typing import Dict, Optional

# Extension → primary language mapping
EXT_MAP = {
    ".py": "Python", ".pyw": "Python",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript",
    ".jsx": "JavaScript",
    ".java": "Java",
    ".go": "Go",
    ".rs": "Rust",
    ".cpp": "C++", ".cxx": "C++", ".cc": "C++",
    ".c": "C",
    ".h": None,   # ambiguous — need content check
    ".rb": "Ruby",
    ".php": "PHP",
    ".cs": "C#",
    ".kt": "Kotlin",
    ".swift": "Swift",
    ".scala": "Scala",
    ".r": "R", ".R": "R",
    ".sh": "Bash", ".bash": "Bash",
    ".sql": "SQL",
}

# Era detection signatures per language
ERA_SIGNATURES = {
    "Python": [
        # Python 2 signals
        (r"\bprint\s+['\"]",          "2.x",  "print as statement"),
        (r"\bprint\s+\(",             None,    None),   # ambiguous print()
        (r"\bxrange\s*\(",            "2.x",  "xrange() — removed in Python 3"),
        (r"\.has_key\s*\(",           "2.x",  "dict.has_key() — removed in Python 3"),
        (r"\bexcept\s+\w+\s*,\s*\w+","2.x",  "except E, e syntax — Python 2 style"),
        (r"\burllib2\b",              "2.x",  "urllib2 — replaced by urllib.request in Python 3"),
        (r"\braw_input\s*\(",         "2.x",  "raw_input() — renamed to input() in Python 3"),
        (r"^#.*coding[:=]\s*(utf-8|latin-1)", "2.x", "explicit encoding declaration — Python 2"),
        (r"\bbasestring\b",           "2.x",  "basestring — removed in Python 3"),
        (r"\bunicode\s*\(",           "2.x",  "unicode() builtin — removed in Python 3"),
        # Python 3.5 and under
        (r"async\s+def|await\s+",     "3.5+", "async/await — Python 3.5+"),
        # F-strings indicate 3.6+
        (r'f["\'].*\{',               "3.6+", "f-strings — Python 3.6+"),
        # Walrus operator 3.8+
        (r":=",                       "3.8+", "walrus operator — Python 3.8+"),
        # match/case 3.10+
        (r"^match\s+\w+",             "3.10+","match/case — Python 3.10+"),
    ],
    "JavaScript": [
        (r"\bvar\s+\w+",              "ES5",  "var declarations — pre-ES6"),
        (r"function\s*\(",            "ES5",  "traditional function syntax"),
        (r"\.then\s*\(",              "ES6",  "promise chains — consider async/await"),
        (r"\bXMLHttpRequest\b",       "ES5",  "XHR — replaced by fetch()"),
        (r"prototype\.",              "ES5",  "prototype-based OOP — pre-class syntax"),
        (r"\brequire\s*\(",           "CJS",  "CommonJS require — consider ES modules"),
        (r"const\s+\w+\s*=\s*\(",    "ES6+", "const declarations — ES6+"),
        (r"=>\s*[{(]",               "ES6+", "arrow functions — ES6+"),
        (r"\basync\s+function\b",     "ES8+", "async/await — ES2017+"),
        (r"import\s+.*from\s+['\"]", "ESM",  "ES modules"),
    ],
    "Java": [
        (r"ArrayList\s+\w+\s*=\s*new\s+ArrayList\s*\(\)", "Java7-", "raw ArrayList — use generics"),
        (r"for\s*\(\s*(int|String)\s+\w+\s*=\s*0", "Java7-", "old-style for loop"),
        (r"StringBuffer\s+",         "Java7-","StringBuffer — use StringBuilder"),
        (r"System\.out\.println",    "Java7-","System.out.println — use a logger"),
        (r"@Override\s+public",      "Java5+","@Override annotation"),
        (r"List<|Map<|Set<",         "Java5+","generics — Java 5+"),
        (r"Optional\.",              "Java8+","Optional — Java 8+"),
        (r"\bstream\(\)\.",          "Java8+","Streams API — Java 8+"),
        (r"var\s+\w+\s*=",           "Java10+","local variable type inference — Java 10+"),
    ],
}


def detect_language(file_path: str, content: str) -> Dict:
    """
    Returns: {language, era, version_hint, extension, confidence}
    """
    ext = Path(file_path).suffix.lower()
    language = EXT_MAP.get(ext)

    # Content-based detection for ambiguous or unknown extensions
    if language is None:
        language = _detect_from_content(content)

    if not language:
        return {
            "language": "Unknown",
            "era": "unknown",
            "version_hint": "",
            "extension": ext,
            "confidence": "low",
        }

    era, hints = _detect_era(language, content)

    return {
        "language": language,
        "era": era,
        "version_hint": "; ".join(hints) if hints else f"{language} (no era markers detected)",
        "extension": ext,
        "confidence": "high" if hints else "medium",
    }


def _detect_from_content(content: str) -> Optional[str]:
    """Detect language from content when extension is ambiguous."""
    lines = content[:2000]  # first ~40 lines
    if re.search(r"^\s*def\s+\w+\s*\(|import\s+\w+|from\s+\w+\s+import", lines, re.MULTILINE):
        return "Python"
    if re.search(r"^\s*function\s+\w+|const\s+\w+\s*=|let\s+\w+", lines, re.MULTILINE):
        return "JavaScript"
    if re.search(r"public\s+(class|interface|enum)\s+\w+", lines):
        return "Java"
    if re.search(r"^package\s+main|^func\s+\w+", lines, re.MULTILINE):
        return "Go"
    if re.search(r"^fn\s+\w+|let\s+mut\s+", lines, re.MULTILINE):
        return "Rust"
    if re.search(r"#include\s*<", lines):
        return "C" if ".h" in lines else "C++"
    return None


def _detect_era(language: str, content: str) -> tuple:
    """Returns (era_string, list_of_hints)."""
    sigs = ERA_SIGNATURES.get(language, [])
    matched_eras = []
    hints = []

    for pattern, era, hint in sigs:
        if re.search(pattern, content, re.MULTILINE):
            if era and era not in matched_eras:
                matched_eras.append(era)
            if hint:
                hints.append(hint)

    if not matched_eras:
        return f"{language} (modern)", hints

    # Oldest era detected is most significant
    era_order = {
        "ES5": 1, "CJS": 1, "Java7-": 1, "2.x": 1,
        "ES6": 2, "Java5+": 2, "3.5+": 2,
        "ES6+": 3, "3.6+": 3, "Java8+": 3,
        "ES8+": 4, "ESM": 4, "3.8+": 4, "Java10+": 4,
        "3.10+": 5,
    }
    matched_eras.sort(key=lambda e: era_order.get(e, 99))
    return matched_eras[0], hints