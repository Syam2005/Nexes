# 🚀 NEXUS — Agentic Codebase Modernization Platform

> **AI-powered code modernization, security scanning, testing, and risk analysis — with a human approval gate.**

NEXUS is an **Agentic Codebase Modernization Platform** that analyzes legacy codebases, detects outdated patterns, identifies security vulnerabilities, proposes **minimal and safe code changes**, runs tests before and after modernization, calculates risk, and generates a detailed report.

Instead of allowing an AI agent to directly modify a codebase, NEXUS follows a **human-in-the-loop approach**:

**AI proposes → Tests validate → Human approves → Only approved changes are committed.**

🌐 **Live Demo:** https://nexus-2-7dg3.onrender.com

---

## ✨ Key Features

### 🔐 Authentication & User Management

* Google OAuth2 authentication
* GitHub OAuth2 integration
* Support for multiple GitHub accounts
* JWT-based sessions
* User profile management
* Persistent analysis history
* SQLite/PostgreSQL database storage

### 📂 Multiple Input Modes

NEXUS supports multiple ways to provide code:

* Single file upload
* Multiple file upload
* GitHub repository URL
* GitHub repository browser
* File-tree based file selection
* Analyze an entire repository
* Automatic CI/CD analysis through GitHub PR webhooks

### 🔍 Security Scanning

Security is performed **before modernization**.

NEXUS integrates:

* **Bandit** — Python security analysis
* **Semgrep** — Static analysis
* **detect-secrets** — Secret detection
* **OSV Scanner** — Dependency vulnerability detection
* **Trivy** — Container and IaC security scanning

> **HIGH severity security findings can block the pull request.**

Security issues are reported to the developer rather than automatically modifying the vulnerable code.

---

# 🤖 Agentic AI Pipeline

NEXUS uses multiple specialized LLM agents instead of relying on a single AI prompt.

### 1. Reader Agent

Analyzes the code and identifies:

* Legacy patterns
* Outdated APIs
* Modernization opportunities
* Relevant code structures

The Reader Agent uses **Groq Llama 3.1 70B** for dynamic reasoning.

### 2. Modernizer Agent

Creates **surgical, minimal code modifications**.

The system validates the original code before applying changes to prevent accidental modifications.

### 3. Risk Scorer Agent

Calculates modernization risk using real project information such as:

* Test results
* Percentage of code changed
* Caller count
* I/O proximity
* Complexity changes

### 4. Documenter Agent

Generates a complete modernization report containing:

* Detected legacy patterns
* Security findings
* Proposed changes
* Test results
* Risk information
* Rollback commands

The report can also be delivered through email.

---

# 🧠 AST-Based Code Understanding

One of the core design decisions of NEXUS is:

> **AST = Ground Truth**

NEXUS uses **Tree-sitter** to parse source code and obtain accurate structural information.

The language detection and AST pipeline supports **40+ programming languages**.

Instead of trusting an LLM to provide line numbers, NEXUS obtains exact positions from the syntax tree.

This helps prevent a major problem with LLM-based code modification:

**LLM hallucinating incorrect line numbers.**

All proposed modifications are validated against the AST before they are applied.

---

# 🔄 End-to-End Workflow

```text
Developer
    │
    ▼
Sign in with Google
    │
    ▼
Connect GitHub
    │
    ▼
Select Repository / Upload Code
    │
    ▼
Language Detection
    │
    ▼
Tree-sitter AST Parsing
    │
    ▼
Security Scanning
    │
    ▼
Reader Agent
    │
    ▼
Modernizer Agent
    │
    ▼
Diff Engine
    │
    ▼
Test Runner
    │
    ▼
Risk Scorer
    │
    ▼
Documenter Agent
    │
    ▼
Human Approval Gate
    │
    ├── Skip Changes
    │
    └── Accept Changes
             │
             ▼
       GitHub Commit / Download
             │
             ▼
          Email Report
```

---

# 🛡️ Security-First Architecture

NEXUS follows a security-first modernization process.

```text
Code Input
    ↓
Security Scan
    ↓
AST Parsing
    ↓
Legacy Detection
    ↓
AI Modernization
    ↓
Diff Validation
    ↓
Tests Before & After
    ↓
Risk Analysis
    ↓
Human Approval
    ↓
Commit
```

A modernization operation cannot simply bypass the security and validation stages.

---

# 🧪 Test Runner

NEXUS automatically detects available testing frameworks, including:

* pytest
* Jest
* JUnit

Tests are executed **before and after modernization**.

This allows NEXUS to detect regressions.

```text
Before Modernization
        ↓
     Run Tests
        ↓
   AI Modification
        ↓
     Run Tests
        ↓
Compare Results
        ↓
Regression?
   ├── YES → BLOCK
   └── NO  → Continue
```

If modernization causes a regression, the proposed change can be blocked.

---

# 🔀 Diff Engine

NEXUS does not blindly replace entire files.

The Diff Engine creates **minimal changes** and allows developers to review each proposed modification.

Developers can:

* Accept individual changes
* Skip individual changes
* Review the risk badge
* Inspect security findings
* Approve only the required modifications

Only approved changes are committed.

---

# 🔗 GitHub Integration

NEXUS integrates directly with GitHub.

Capabilities include:

* Connect GitHub accounts
* Disconnect accounts
* Load repositories
* Browse repository file trees
* Select individual files
* Analyze complete repositories
* Receive pull-request webhooks
* Validate webhook signatures
* Commit approved changes
* Download modified files

Webhook requests are protected using **HMAC-SHA256 signature verification**.

---

# ⚡ Real-Time Pipeline

NEXUS provides a live pipeline trace through **WebSocket communication**.

The UI can display the current agent/pipeline state while analysis is running.

Important design principle:

> **No analysis state is stored in browser localStorage.**

Analysis history and application state are persisted through the backend database.

---

# 📊 Reports & History

Users can access previous analyses through the history section.

Reports can be:

* Re-opened
* Filtered by programming language
* Filtered by risk
* Filtered by date
* Emailed to the user's Google-login email address

The platform maintains persistent analysis history instead of depending on browser localStorage.

---

# 📧 Email Reports

After an analysis is completed, NEXUS can send a complete modernization report to the authenticated user's email.

The report contains information such as:

* Security findings
* Legacy code findings
* Proposed changes
* Test results
* Risk information
* Rollback instructions

Email functionality uses services such as **SendGrid/Resend**.

---

# 🏗️ Technical Architecture

```text
                     ┌──────────────────────┐
                     │     React Frontend   │
                     │   Vite + Tailwind    │
                     └──────────┬───────────┘
                                │
                         WebSocket / API
                                │
                     ┌──────────▼───────────┐
                     │    FastAPI Backend   │
                     └──────────┬───────────┘
                                │
          ┌─────────────────────┼─────────────────────┐
          │                     │                     │
          ▼                     ▼                     ▼
   Tree-sitter             Security Layer        GitHub API
   AST Parser              Bandit/Semgrep        PyGitHub
                            OSV/Trivy
          │
          ▼
   ┌─────────────────────────────────────┐
   │          Agent Pipeline             │
   │                                     │
   │ Reader → Modernizer → Risk → Docs  │
   └──────────────────┬──────────────────┘
                      │
                      ▼
                Diff Engine
                      │
                      ▼
                 Test Runner
                      │
                      ▼
              Human Approval Gate
                      │
                      ▼
              GitHub Commit
```

---

# 🛠️ Tech Stack

| Category           | Technologies                                |
| ------------------ | ------------------------------------------- |
| Frontend           | React, Vite, Tailwind CSS                   |
| Backend            | FastAPI                                     |
| AI/LLM             | Groq Llama 3.1 70B, Ollama fallback         |
| Agent Framework    | LangChain                                   |
| Code Parsing       | Tree-sitter, py-tree-sitter                 |
| Security           | Bandit, Semgrep, detect-secrets, OSV, Trivy |
| Database           | SQLite / PostgreSQL                         |
| Authentication     | Google OAuth2, GitHub OAuth2, JWT           |
| GitHub Integration | PyGitHub                                    |
| Real-Time          | WebSocket                                   |
| Testing            | pytest, Jest, JUnit                         |
| Frontend Diff      | react-diff-viewer                           |
| CI/CD              | GitHub Actions                              |
| Email              | SendGrid / Resend                           |
| Deployment         | Render / Railway                            |

The project uses a free/open-source-oriented stack with a stated total stack cost of **₹0**.

---

# 🌍 Language Support

NEXUS uses Tree-sitter for parsing and supports **40+ programming languages**.

The AST-based approach allows the platform to understand code structure without relying exclusively on language-specific hardcoded modernization rules.

---

# 🧩 Key Design Decisions

### AST as Ground Truth

LLMs are not trusted for exact source-code locations.

Tree-sitter provides the authoritative source positions.

### Security First

Security scans are performed before modernization.

### No Hardcoded Modernization Rules

The Reader and Modernizer agents reason dynamically based on the language, code structure, and context.

### Human-in-the-Loop

AI does not automatically commit changes.

Every proposed diff requires human approval.

### Test Before & After

Tests are executed before and after modernization to detect regressions.

### Minimal Changes

NEXUS focuses on surgical modifications rather than unnecessarily rewriting complete files.


# 📈 Project Highlights

* 🌐 **40+ programming languages**
* 🔄 **11-layer end-to-end pipeline**
* 🤖 **4 specialized LLM agents**
* 🔐 Multiple security scanners
* 🧪 Automated before/after testing
* 🔀 Minimal diff generation
* 👤 Human approval for every change
* 🔗 GitHub PR integration
* ⚡ Real-time WebSocket pipeline
* 📧 Automated email reports
* 📊 Persistent analysis history
* 💰 Free/open-source-oriented stack

The presentation identifies these as the project's key impact numbers.

---


## ⭐ Built with AI. Validated with Tests. Approved by Humans.

**NEXUS — Agentic Codebase Modernization Platform**
