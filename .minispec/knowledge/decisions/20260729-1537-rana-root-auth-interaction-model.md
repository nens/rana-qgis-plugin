---
type: decision
id: 20260729-1537-rana-root-auth-interaction-model
date: 2026-07-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/
  - .minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md
tags: [auth, browser, context-menu, interactions]
participants: [engineer, implementation-agent]
---

# Use a single Rana root item with state-aware actions

## Context

The Browser must clearly support login/logout/session actions without relying on plugin top-menu entries.

## Options Considered

### Option 1: Single root with dynamic actions
- ✅ Minimal visual clutter
- ✅ Familiar context menu pattern in Browser
- ❌ Requires careful state transitions

### Option 2: Dedicated auth child subtree
- ✅ Explicit status visibility
- ❌ Clutters tree and diverges from expected datasource ergonomics

### Option 3: Root + status child hybrid
- ✅ Good status visibility
- ❌ More item complexity without strong user request

## Decision

We chose **Option 1**, with additional explicit behavior:
- Rana root is always visible.
- Logged out:
  - double-click starts login
  - context actions: `Login`, `Settings`
  - no tenant action
- Logged in:
  - context actions: `Logout`, `Switch tenant`, `Settings`

## Consequences

### Positive
- ✅ Clear, compact Browser UX
- ✅ Preserves discoverability through both double-click and context menu

### Negative
- ⚠️ Requires strict synchronization between auth state and menu/action refresh

### Neutral
- Root label remains stable (`Rana`).

## Code References

- Legacy behavior reference: `rana_qgis_plugin/legacy/rana_qgis_plugin.py:login(), logout(), add_rana_menu()`
- Design spec: `.minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md`

## Notes

This interaction model intentionally removes logged-out tenant editing from the context menu.
