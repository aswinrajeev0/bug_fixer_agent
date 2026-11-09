# ⚡ HealCode: Self-Healing Bug Fixer & Test Agent

An autonomous, resilient agent powered by **Google Gemini** that monitors your test suites, pinpoints root causes with AST-aware static analysis, synthesizes minimal surgical code patches, and verifies fixes through an iterative self-healing feedback loop.

---

## 🌟 Key Features

- **Autonomous Test Suite Monitoring**: Runs `pytest` or `unittest` and intercepts failures, stack traces, and exit codes.
- **AST-Aware Triage & Diagnostic Engine**:
  - Isolates culprit frames from test harness frames.
  - Automatically correlates assertion failures with tested source modules and enclosing function/class definitions.
- **Google Gemini Integration**:
  - Leverages Google Gemini (`gemini-2.5-flash` or `gemini-2.5-pro`) via the official `google-genai` SDK.
  - Generates structured, minimal surgical fixes with strict schema validation.
  - Optional automatic regression test synthesis.
- **Sandbox Safety & Git Checkpointing**:
  - AST-based pre-validation catches `SyntaxError` before any tests run.
  - Automatic Git checkpointing with safe one-click rollback if healing attempts fail or the user rejects changes.
  - Optional auto-commit of verified fixes with structured commit messages.
- **Interactive Rich Terminal UI**:
  - Syntax-highlighted diffs, root cause explanation cards, live execution spinners, and summary metrics.

---

## 🔄 Self-Healing Feedback Loop

```text
[ Run Test Suite ] ──► (All Passed?) ──► [ Complete: Zero Regressions ]
       │ No
       ▼
[ Traceback & AST Context Extractor ] ──► (Pinpoint Culprit Frame & Scope)
       │
       ▼
[ Gemini Reasoning Engine ] ──► (Analyze Root Cause & Generate Patch)
       │
       ▼
[ AST Syntax Pre-Validator ] ──► (Invalid Syntax?) ──► [ Reject & Re-prompt ]
       │ Valid
       ▼
[ Apply Patch to Sandbox ]
       │
       ▼
[ Re-execute Test Suite ] ──► (Passed?) ──► [ Verified Fix: Commit & Done ]
       │ Failed
       ▼
(Attempts < Max Retries?) ──► [ Feed New Error Back into Gemini ] ──► (Loop)
       │ Exhausted
       ▼
[ Safe Git/File Rollback ]
```

---

## 🚀 Quickstart

### 1. Installation

```bash
# Clone and enter directory
cd bug_fixer_agent

# Create and activate virtual environment
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux / macOS
source .venv/bin/activate

# Install dependencies and HealCode
pip install -e .
```

### 2. Configure Gemini API Key

Obtain an API key from [Google AI Studio](https://aistudio.google.com/).

```bash
# Option A: Environment Variable
export GEMINI_API_KEY="your-gemini-api-key"        # Linux/macOS
$env:GEMINI_API_KEY="your-gemini-api-key"          # PowerShell

# Option B: .env file
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY
```

---

## 💻 CLI Commands

### 1. `healcode heal`
Runs the test suite, automatically diagnoses any failing tests, synthesizes patches via Gemini, and verifies the resolution in an iterative loop.

```bash
# Run on full project test suite
healcode heal

# Target a specific test file or directory
healcode heal tests/test_calculator.py

# Customize model and retries
healcode heal --model gemini-2.5-pro --max-retries 4

# Run in non-interactive CI mode with auto-commit
healcode heal --non-interactive --auto-commit
```

### 2. `healcode scan`
Triage-only mode. Diagnoses test failures, identifies the suspected culprit file and line number without modifying any files or calling the LLM.

```bash
healcode scan
healcode scan --dir examples/buggy_calculator
```

### 3. `healcode info`
Displays current system environment, Git repository status, active model, and API configuration.

```bash
healcode info
```

---

## 🧪 Included Buggy Demo

An example buggy project with deliberate logical bugs (`ZeroDivisionError`, inverted discount calculation, unsorted median calculation) is included in `examples/buggy_calculator/`.

To inspect the failures:
```bash
healcode scan --dir examples/buggy_calculator
```

To run the autonomous self-healing agent on it:
```bash
healcode heal --dir examples/buggy_calculator
```

---

## 🏗️ Project Architecture

```
bug_fixer_agent/
├── healcode/
│   ├── cli.py                  # Typer / Rich CLI commands (heal, scan, info)
│   ├── config.py               # Pydantic configuration & .env loading
│   ├── core/
│   │   ├── state.py            # Diagnostic & iteration state management
│   │   ├── loop.py             # Resilient self-healing state-machine engine
│   ├── runners/
│   │   ├── base.py             # Abstract test runner & TestRunResult model
│   │   ├── pytest_runner.py    # Pytest execution & granular output parser
│   │   └── unittest_runner.py  # Python unittest execution & parser
│   ├── analyzer/
│   │   ├── traceback_parser.py # Stack trace analyzer & culprit isolator
│   │   └── code_context.py     # AST-based scope & source extractor
│   ├── agent/
│   │   ├── models.py           # Structured patch & proposal Pydantic schemas
│   │   ├── prompts.py          # Few-shot prompts for surgical code repair
│   │   └── gemini_client.py    # Official google-genai SDK wrapper
│   ├── sandbox/
│   │   ├── patcher.py          # Diff generator, syntax validator & applicator
│   │   └── git_manager.py      # Git checkpointing, commits & clean rollbacks
│   └── ui/
│       ├── console.py          # Rich console singleton & theme
│       └── views.py            # Pretty panels, diff renderers, & report cards
├── examples/
│   └── buggy_calculator/       # Out-of-the-box demo repository with real bugs
├── tests/                      # Full test suite for the agent itself
├── pyproject.toml
└── requirements.txt
```

---

## 🛡️ Running Unit Tests

To run the unit tests verifying HealCode's components:
```bash
pytest tests -v
```
All unit tests run offline using mocks without consuming API credits.
