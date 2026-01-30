---
applyTo: '**'
---
**You are strictly bound by the external rule files in this repository.**
Because these rules are modular, you must **actively read** the relevant file before answering complex queries.

# Global Agent Protocols

## 1. General Hygiene
- **Commit Messages:** Use Conventional Commits (feat, fix, docs, chore, test).
- **Comments:** Do not leave commented-out code. Delete it.
- **Documentation:** Keep README files up-to-date when changing functionality.
- **Code Formatting:** Before generating or modifying code, read `.editorconfig` in the project root to determine:
  - Indentation style (spaces vs. tabs)
  - Indentation size (2 or 4 spaces)
  - Line endings (LF vs. CRLF)
  - Trailing whitespace rules
  Apply these settings consistently in all generated code.

## 2. Version Control Protocol
- **No Auto-Commit:** You are strictly FORBIDDEN from running `git commit`, `git push`, or `git merge` autonomously.
- **Review First:** You may `git add` files to stage them, but you must ask for explicit user confirmation before committing.
- **Commit Messages:** When requested to commit, always draft the commit message for the user to review first.

## 3. Python Bestpractices

### Environment Management
- **Tooling:** STRICTLY use `uv` for all package operations.
- **Execution:** ALWAYS use `uv run <command>` (e.g., `uv run python`, `uv run pytest`).
- **Do Not:** Never attempt to source `bin/activate`. It fails in non-persistent agent shells.

### Code Standards
- **Style:** Adhere to PEP 8. Configuration in `pyproject.toml` and `mypy.ini`.
- **Type Hints:** Required for all function signatures. Use mypy for type checking.
- **Imports:** Absolute imports preferred instead of relative imports.
- **Docstrings:** Use Google-style docstrings for all public APIs.
- **Whitespace:** ALWAYS trim trailing spaces from all lines. No trailing whitespace allowed.

## 4. Documentation Standards: Usage vs. Architecture

### 1. Separation of Concerns
Documentation must be split into two distinct categories:
- **Usage (The "How"):** Instructions for end-users or developers on running code (e.g., CLI commands, function arguments).
- **Architecture (The "Why"):** Explanations of design choices, trade-offs, and technology selection.

### 2. Location of Documentation
- **Usage Docs:** Go into `README.md` files and standard function/class **Docstrings**.
- **Architecture Docs:** MUST be placed in a dedicated `docs/architecture/` folder (or a distinct `## Architecture & Design` section at the bottom of the root README).

### 3. The "Rationale" Requirement
When documenting architecture, you must explicitly answer "Why?" for major decisions.
- **Bad:** "We use Pydantic." (Statement of fact)
- **Good:** "We chose **Pydantic** over standard `dataclasses` because we require strict **runtime validation** and type coercion for the user-provided YAML files, which dataclasses do not provide natively."
