"""System and user prompts for the Gemini Self-Healing Bug Fixer Agent."""

SYSTEM_PROMPT = """You are HealCode, an expert Principal Software Engineer and Autonomous Bug Fixing & Test Specialist.
Your goal is to inspect failing test suites, diagnose root causes, and generate minimal, robust, production-grade fixes.

CORE PRINCIPLES:
1. MINIMAL SURGICAL FIXES:
   - Make the smallest change necessary to fix the issue correctly.
   - Do not refactor unrelated code, change variable names arbitrarily, or reformat styling.
   - Preserve all existing comments, docstrings, and type hints.

2. FIX THE IMPLEMENTATION, NOT THE TEST:
   - When a test fails because the code is incorrect, fix the source code!
   - Only modify the test file if the test itself contains an objective bug (e.g. wrong assertion, outdated mock).

3. REGRESSION RESISTANT:
   - Ensure boundary conditions, None values, edge cases, and type safety are respected.
   - Do not break existing passing functionality.

4. COMPLETE FILE OUTPUT:
   - In each `FilePatch`, provide the COMPLETE, valid Python code for `new_content`.
   - Never use ellipses `...` or leave comments like "# Rest of code remains the same". Always supply the full file content.

5. REGRESSION TEST CASE:
   - Whenever feasible, provide a clean, dedicated test function in `regression_test_code` that asserts the bug is fixed.
"""

def build_initial_heal_prompt(
    test_name: str,
    error_type: str,
    error_message: str,
    traceback_snippet: str,
    culprit_file_path: str,
    culprit_file_content: str,
    test_file_path: str = "",
    test_file_content: str = "",
    other_context: str = "",
) -> str:
    prompt = f"""### FAILED TEST INVESTIGATION
Test Name: `{test_name}`
Error Type: `{error_type}`
Error Message: {error_message}

### TRACEBACK:
```
{traceback_snippet}
```

### PRIMARY CULPRIT FILE: `{culprit_file_path}`
```python
{culprit_file_content}
```
"""
    if test_file_path and test_file_content:
        prompt += f"""
### FAILING TEST FILE: `{test_file_path}`
```python
{test_file_content}
```
"""
    if other_context:
        prompt += f"""
### ADDITIONAL CODE CONTEXT:
{other_context}
"""

    prompt += """
Please analyze this failure:
1. Explain the root cause of the bug.
2. Formulate a fix hypothesis.
3. Provide the full file patch(es) with the complete updated code.
4. Optionally provide a new regression test function.
"""
    return prompt

def build_retry_heal_prompt(
    attempt_num: int,
    previous_hypothesis: str,
    previous_diff: str,
    new_error_type: str,
    new_error_message: str,
    new_traceback: str,
    current_files_content: str,
) -> str:
    return f"""### RE-ATTEMPT: FIX ITERATION {attempt_num} FAILED
Your previous attempt to fix the bug did not succeed, or introduced a new error.

#### PREVIOUS FIX HYPOTHESIS:
{previous_hypothesis}

#### PREVIOUS PATCH APPLIED:
```diff
{previous_diff}
```

#### NEW TEST FAILURE:
Error Type: `{new_error_type}`
Error Message: {new_error_message}

#### NEW TRACEBACK:
```
{new_traceback}
```

#### CURRENT FILE CONTENT:
{current_files_content}

Re-evaluate your hypothesis. What did the previous patch miss or break?
Provide a revised, corrected patch with complete updated file contents.
"""
