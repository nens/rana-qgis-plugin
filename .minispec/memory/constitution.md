# Rana QGIS Plugin Constitution

## Core Principles

### I. Stability

The plugin must be rock-solid. No regressions, graceful handling of edge cases, and predictable behavior under normal use. Users cannot upgrade easily, so bugs persist in their environments for months or years. Quality gates are non-negotiable.

**What this means:**
- No crashes on normal user behavior or unexpected inputs
- Authentication, file operations, and threading must work reliably even under concurrent load
- Manual testing coverage across all critical UI paths (auth, file upload/download, style operations) after changes
- Test coverage for utility functions where feasible; e2e tests grow gradually

### II. Code Clarity & Maintainability

Clear, testable, and understandable code is essential for stability. Maintainable code enables future changes without introducing subtle bugs.

**What this means:**
- Follow PEP8 as enforced by flake8/black; 4 spaces, no tabs
- Explicit imports; no wildcards
- Docstrings for all public functions and classes
- QGIS/PyQt imports only (never direct PyQt or Qt imports)
- Qt 5.15.13 compatibility required; Qt 6 compatibility where possible
- Signal chains, thread lifecycle, and UI state patterns will evolve as documented practices

**Known pain points to address over time:**
- Signal tracing: signal chains are hard to follow
- Thread lifecycle: plugin reload can cause crashes; explicit cleanup patterns needed
- UI state management: disabling/enabling UI involves error-prone bookkeeping; cleaner patterns needed

## Technology Stack & Constraints

- **QGIS 3.x** with Qt 5.15.13 (Qt 6 compatible where possible)
- **Python 3** with PEP8 enforcement
- **Docker-based development** for isolation and consistency
- **Authentication:** OAuth2 for Rana, 3Di personal API key via Rana API
- **Testing:** Unit tests (pytest) for utility functions; e2e tests for critical paths; manual testing for UI workflows
- **Pre-commit hooks:** Code quality checks before commit
- **CI/CD:** Tests must pass before merge; linting enforced

## Development Workflow

See `AGENTS.md` for setup, testing, and commit conventions.

---

## MiniSpec Preferences

### Review Chunk Size

**Medium (40-80 lines per chunk)**

Balances steady pace with thorough review, appropriate for Qt/threading complexity.

### Documentation Review Policy

**Review-all**

All documentation changes (decisions, patterns, modules) are reviewed before commit. This ensures consistency as patterns evolve.

### Autonomy Level

**Always-confirm**

I pause after each chunk and wait for your approval before proceeding. Maximum safety for a stability-critical project.

### Design Evolution Handling

**Always-discuss**

Any deviation from the original design is discussed before continuing. This prevents stability issues from divergent implementations, especially with threading and signals.

### Walkthrough Depth

**Standard**

Architecture + key patterns + conventions (15-20 min), suitable for navigating the codebase effectively.

### Complexity Tolerance

Calibrates how I approach complexity during implementation—keeping changes focused and maintainable.

**Change Size:**
**Minimal first** — Show the smallest change that works, then you decide if you want the thorough version. This reduces review burden and keeps the codebase simple. If a more thorough version is worth considering, I'll mention it after presenting the minimal one.

**Abstraction Threshold:**
**Conservative** — Only extract when code is duplicated 3+ times or exceeds 50 lines. Forces clarity upfront and prevents premature abstraction. Inline over extract unless truly necessary.

**Review Findings:**
**Your call** — When a code review tool flags an issue, I'll present it explicitly and let you decide: fix it, decline it, or defer it as a follow-up task. Not every finding deserves a commit.

**Deletion Permission:**
**Yes** — I can propose removing unnecessary code during feature tasks. Dead code, unused imports, or unnecessary abstractions will be flagged: *"While implementing this, I noticed [X] appears unused. Want me to remove it?"*

---

## Governance

The constitution is the source of truth for development standards. Amendments require discussion. MiniSpec preferences can be adjusted per-feature if needed, but should be agreed upon first.

---

## Skills Governance

### File locations

Spec and plan files always go to `.minispec/specs/`. Never to `docs/superpowers/specs/`, the project root `specs/`, or any other location.

### Branch creation

The AI must not create git branches on its own initiative. No `git checkout -b` or equivalent unless the user explicitly requests it.

### Skill suppression

When a minispec command is invoked, its built-in workflow is the authority. External skills must not be invoked if the command already handles that workflow. Per-command suppression:

| Command | Suppressed skills |
|---|---|
| `/minispec.design` | `brainstorming`, `writing-plans` |
| `/minispec.tasks` | `writing-plans` |
| `/minispec.next` | `test-driven-development`, `subagent-driven-development`, `executing-plans` |
| `/minispec.analyze` | `requesting-code-review` |

**Version:** 1.2.0 | **Ratified:** 2026-04-15 | **Last Amended:** 2026-06-18
