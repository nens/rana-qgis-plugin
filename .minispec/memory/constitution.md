# Rana QGIS Data Provider Constitution

## Core Principles

### I. Stability & UX

Code must be stable for a good user experience. Correctness is non-negotiable. The user must always be informed when the UI is locked and why.

### II. Maintainability

Clear, readable code. Avoid tangled signal chains and scattered state management. The rewrite exists precisely to leave those problems behind.

### III. Pragmatic Testing

Tests must test real behavior, not mocks. Avoid heavy mocking that just tests the mock itself. E2E tests cover happy paths and mimic user clicks (as close to real user interaction as possible). Always need explicit permission to add E2E tests.

### IV. Incremental Vertical Slices

Build in minimal end-to-end increments. Each slice should be manually testable in isolation. This keeps testing focused and enables parallel development later.

### V. Responsive UI

Quick actions can be synchronous; long-running actions must not freeze the UI. Use threading when necessary, but choose the right approach for the situation — don't copy legacy threading patterns without evaluating them critically.

### VI. Legacy as Reference, Not Authority

The old code shows what was done and how, but it is not a template. Point out flaws and suggest improvements rather than reproducing existing patterns uncritically.

## Technology Stack

- Python, QGIS 4.x, Qt 6 (via QGIS namespace only)
- Custom `QgsDataItemProvider` as primary integration pattern
- PEP8 via black/flake8, pathlib over os.path
- Docker-based development and testing environment
- OAuth2 authentication against Rana backend

## Development Workflow

- All commits must pass unit tests and pre-commit hooks
- E2E tests run in CI on PRs, not locally after every change
- Imperative commit messages (e.g. "Fix upgrade error in postprocess")
- Feature branches with PR review required
- UI changes require indication of which paths need manual testing

## MiniSpec Specifications

- `.minispec/specs/` is the sole location for feature designs and task lists.
- Do not create or use a root-level `specs/` directory.
- Reference knowledge-base decisions from a feature spec as `../../knowledge/decisions/<id>.md`.

---

## MiniSpec Preferences

### Review Chunk Size

adaptive — AI assesses complexity and suggests appropriate size per task.

### Documentation Review Policy

trust-ai — AI handles all documentation autonomously. Engineer can always review in git.

### Autonomy Level

always-confirm — AI always pauses for engineer approval before proceeding.

### Design Evolution Handling

flag-and-continue — AI flags issues and proposes spec updates; continues if minor, stops for major deviations.

### Complexity Tolerance

- **Change size:** Minimal first — show the smallest working change, engineer decides if more is needed.
- **Abstraction threshold:** Conservative — extract only when duplicated 3+ times or exceeds 50 lines.
- **Review findings:** Triage first — present findings, ask whether worth fixing before writing code.
- **Deletion permission:** Yes — propose removing unnecessary code.

---

## Governance

Constitution captures project values and pairing preferences. It can be amended at any time through discussion. MiniSpec preferences can be adjusted per-feature if needed.

**Version**: 1.0.0 | **Ratified**: 2026-07-31 | **Last Amended**: 2026-07-31
