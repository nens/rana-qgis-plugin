---
type: decision
id: 20260729-1539-settings-scope-backend-url-only
date: 2026-07-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/utils/settings.py
  - rana_qgis_plugin/
  - .minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md
tags: [settings, ux, auth]
participants: [engineer, implementation-agent]
---

# Limit settings dialog scope to backend URL

## Context

The first auth bootstrap increment needs settings support, but broader authentication parameter editing increases risk and support burden.

## Options Considered

### Option 1: Backend URL only
- ✅ Minimal and focused first increment
- ✅ Lower risk of misconfiguration
- ❌ Less flexibility for advanced debugging

### Option 2: Backend URL + Cognito client IDs
- ✅ More configurable
- ❌ More user-facing complexity
- ❌ Higher risk of broken auth by accidental edits

## Decision

We chose **Option 1**: expose only backend URL in settings for this increment.

## Consequences

### Positive
- ✅ Clear and constrained UI
- ✅ Reduced chance of auth breakage due to configuration edits

### Negative
- ⚠️ Advanced overrides still require non-UI configuration path

### Neutral
- Existing client ID defaults remain in settings initialization.

## Code References

- Existing settings defaults: `rana_qgis_plugin/utils/settings.py:initialize_settings()`
- Design spec: `.minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md`

## Notes

Scope can be expanded in a future decision once base flow is stable.
