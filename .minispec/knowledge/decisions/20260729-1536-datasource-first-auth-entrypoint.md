---
type: decision
id: 20260729-1536-datasource-first-auth-entrypoint
date: 2026-07-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/
  - .minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md
tags: [auth, browser, qgsdataitemprovider, ux]
participants: [engineer, implementation-agent]
---

# Make auth datasource-first

## Context

The redesign targets a custom `QgsDataItemProvider` flow. Legacy auth is menu-driven from `RanaQgisPlugin.add_rana_menu()`, but the desired final UX is centered in Browser datasource interactions.

## Options Considered

### Option 1: Plugin menu only
- ✅ Closest to legacy
- ✅ Lowest implementation delta
- ❌ Does not match datasource-first product direction

### Option 2: Datasource only
- ✅ Aligns with final product direction
- ✅ Keeps Browser as primary interaction surface
- ❌ Requires additional Browser action/state handling

### Option 3: Hybrid menu + datasource
- ✅ Backward familiar
- ✅ Redundant entry points
- ❌ More UI surface and duplication to maintain

## Decision

We chose **Option 2 (Datasource only)** to align this redesign with the intended end-state UX and avoid long-term split between menu and Browser interaction models.

## Consequences

### Positive
- ✅ Clear single interaction surface for auth/session actions
- ✅ Better fit for custom `QgsDataItemProvider` architecture

### Negative
- ⚠️ Requires explicit discoverability in Browser item behaviors
- ⚠️ Existing menu users need transition guidance

### Neutral
- Legacy menu code remains reference-only, not imported.

## Code References

- Legacy menu auth model: `rana_qgis_plugin/legacy/rana_qgis_plugin.py:add_rana_menu()`
- Feature design: `.minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md`

## Notes

This decision is intentionally scoped to this auth bootstrap increment.
