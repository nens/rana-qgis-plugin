# Agent Instructions

This file contains conventions and instructions for AI agents working in this repository.
See `.minispec/memory/constitution.md` for development principles and standards.

## Development Workflow

- All commits must pass unit tests and pre-commit hooks
- E2E tests are run by CI on PRs; do not run them locally after every change or commit
- For all changes: provide indication of which UI paths need manual testing
- Add unit tests for new utility functions where feasible
- Design decisions and patterns will be documented and reviewed before implementation

See the [README](README.md#local-development-notes) for setup and testing instructions.

## MiniSpec Specifications

- `.minispec/specs/` is the sole location for feature designs and task lists.
- Do not create or use a root-level `specs/` directory.
- Reference knowledge-base decisions from a feature spec as `../../knowledge/decisions/<id>.md`.

## Git

- Never `git add` pre-existing untracked files. Some files in this repo are intentionally uncommitted and not in `.gitignore`.
- Only commit files you created or modified as part of the current task.

## Testing Philosophy

- Tests must test real behavior. If heavy mocking is needed, reconsider whether the test is actually testing the mock rather than the code.
- E2E tests mimic user interaction (clicking, typing). You may suggest E2E tests but always need explicit permission to add them.
- Prefer `pytest.mark.parametrize` when it eliminates significant duplication, but keep assertions readable — a parametrized test with cryptic expected values is worse than a few explicit cases.

## Legacy Code

- The legacy plugin code exists in this repo as reference. Use it to understand what was done and how, but do not assume its patterns are correct.
- Threading patterns in legacy are known to have lifecycle issues. Evaluate the right approach for the situation rather than copying.
- Point out flaws and suggest improvements when referencing legacy code.
- You never need to fix anything in the legacy code!

## Commit Messages

Use short, imperative commit messages (e.g. "Fix upgrade error in postprocess"). No need to reference ticket numbers.

## Branch Naming

- Bug fixes: `bug_<ticket>_<short_description>`
- Features: `feat_<ticket>_<short_description>`
- Use underscores to separate all words
- Keep descriptions concise — a few words after the ticket number is enough
- Examples: `bug_4038_upgrade_error`, `feat_123_foo_bar`

**Before creating a branch:**
- If the type is unclear (bug vs. feature), ask
- If no ticket number was provided, ask for one

## Python Conventions

- Do not prefix module-level functions with `_` to mark them as private. In a module-of-functions design, visibility is expressed through documentation and explicit imports, not name mangling. Reserve `_` for cases where a function is genuinely dangerous to call out of context (e.g. assumes a lock is already held).
- Don't add section comments between functions, methods or tests; naming should be enough.
- Prefer pathlib over os.path

## Software versions
- Code must work with QGIS 4.x
- Code must work with QT6
