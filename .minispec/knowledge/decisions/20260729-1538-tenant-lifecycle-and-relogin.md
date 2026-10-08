---
type: decision
id: 20260729-1538-tenant-lifecycle-and-relogin
date: 2026-07-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/
  - rana_qgis_plugin/utils/settings.py
  - .minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md
tags: [auth, tenant, settings, oauth2]
participants: [engineer, implementation-agent]
---

# Preserve tenant memory and enforce re-login on tenant switch

## Context

Legacy behavior remembers tenant across sessions and asks for tenant only when missing. The redesign must keep this while ensuring tenant switch semantics remain safe.

## Options Considered

### Option 1: Allow tenant switch without re-login
- ✅ Faster interaction
- ❌ Risk of stale/invalid tenant-scoped auth context
- ❌ Ambiguous token/session correctness

### Option 2: Tenant switch requires re-login
- ✅ Explicitly correct auth lifecycle
- ✅ Predictable and safer state handling
- ❌ Additional user step during switch

## Decision

We chose **Option 2**.

Rules:
- Login uses stored tenant when present.
- If no tenant exists, login prompts for tenant and persists it.
- Logged-out context menu does not expose tenant change.
- Switching tenant while logged in invalidates current auth and runs login flow again.
- Sign-in method selection is prompted each login attempt (not persisted).

## Consequences

### Positive
- ✅ Avoids hidden auth/session mismatch after tenant change
- ✅ Matches established user expectation for remembered tenant

### Negative
- ⚠️ Tenant switching is slower due to re-authentication

### Neutral
- Tenant remains in settings as durable preference.

## Code References

- Tenant persistence today: `rana_qgis_plugin/utils/settings.py:set_tenant_id(), get_tenant_id()`
- Legacy login tenant handling: `rana_qgis_plugin/legacy/auth.py:setup_oauth2()`
- Design spec: `.minispec/specs/20260729-1536-rana-qgsdataitemprovider-auth-bootstrap/design.md`

## Notes

This keeps behavior familiar while strengthening correctness guarantees.
