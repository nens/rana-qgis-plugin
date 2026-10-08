# Conventions

*Code conventions and patterns for the Rana QGIS plugin.*

## Python & Code Style

- **PEP8:** Enforced via flake8/black; 4 spaces, no tabs
- **Imports:** Explicit only; no wildcard imports
- **Qt Imports:** Only via QGIS namespace (`from qgis.PyQt.QtCore import ...`); never direct PyQt or Qt
- **Compatibility:** Qt 5.15.13 required; Qt 6 compatible where possible
- **Docstrings:** All public functions and classes must have docstrings

## Testing

- Unit tests for utility functions where feasible
- E2e tests for critical user workflows
- Manual testing guidance required for UI changes (indicate which paths need testing)
- Tests must pass before commit

## Emerging Patterns

*The following patterns will be documented as they're established:*

- Signal documentation and tracing patterns
- Thread lifecycle and cleanup patterns
- UI state management patterns

See `.minispec/knowledge/patterns/` for detailed pattern documentation as it evolves.

---

**Last Updated:** 2026-04-15
