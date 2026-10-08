---
type: decision
id: 20260729-1540-auth-success-visibility
date: 2026-07-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/
  - .minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md
tags: [ux, auth, browser, tooltip]
participants: [engineer, implementation-agent]
---

# Show auth status via tooltip plus action state and message bar

## Context

Users need to see whether login succeeded. A full extra status child in Browser was considered but not required.

## Options Considered

### Option 1: Tooltip + state-aware actions + message bar
- ✅ Lightweight and unobtrusive
- ✅ Works with existing Browser interaction model
- ❌ Tooltip requires hover to inspect details

### Option 2: Add explicit status child item
- ✅ Always visible status text
- ❌ Extra tree clutter and additional item management

### Option 3: Message bar only
- ✅ Simple to implement
- ❌ Status not persistent/discoverable after message fades

## Decision

We chose **Option 1**.

Behavior:
- Root tooltip communicates auth state (logged out/in/error).
- Context menu action set reflects state (`Login` vs `Logout/Switch tenant`).
- Message bar provides immediate success/failure feedback.

## Consequences

### Positive
- ✅ Clear but compact feedback model
- ✅ No extra Browser node noise

### Negative
- ⚠️ Some users may miss tooltip details if they never hover

### Neutral
- Root label stays stable as `Rana`.

## Code References

- Legacy user feedback references: `rana_qgis_plugin/legacy/rana_qgis_plugin.py` (`bar_info`, menu refresh)
- Design spec: `.minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md`

## Notes

If usability testing shows poor discoverability, a status child can be reconsidered in a follow-up decision.
