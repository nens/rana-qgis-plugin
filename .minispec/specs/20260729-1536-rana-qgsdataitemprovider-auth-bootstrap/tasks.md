---
feature: rana-qgsdataitemprovider-auth-bootstrap
status: in-progress
created: 2026-07-29
chunk_size: medium
total_tasks: 10
estimated_lines: 490
---

# Rana QgsDataItemProvider Auth Bootstrap Tasks

## Overview

Introduces a `QgsDataItemProvider`-driven entry point for authentication and tenant-aware browsing, replacing legacy menu-first auth. Covers `RanaAuthManager` (auth state machine), `RanaDataItemProvider` + `RanaRootDataItem` (Browser integration), `RanaSettingsDialog` (backend URL only), plugin entrypoint wiring, and full removal of legacy auth UI.

## Task List

### Foundation

#### Task 0: Developer documentation — login/logout flow
- **Estimate:** ~40 lines (Markdown + Mermaid)
- **Files:** `doc/auth-flow.md` (new)
- **Depends on:** None

---

#### Task 1: Auth state model + `is_authenticated()` (TDD)
- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/auth.py` (new), `tests/test_auth.py` (new)
- **Depends on:** Task 0

---

#### Task 2: Logout + URL-change-forces-logout (TDD)
- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/auth.py`, `tests/test_auth.py`
- **Depends on:** Task 1

---

### Core Implementation

#### Task 3a: Login — tenant resolution + identity provider fetch (TDD)
- **Estimate:** ~65 lines
- **Files:** `rana_qgis_plugin/auth.py`, `tests/test_auth.py`
- **Depends on:** Task 2

#### Task 3b: Login — OAuth2 config creation + auth completion (TDD)
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/auth.py`, `tests/test_auth.py`
- **Depends on:** Task 3a

#### Task 4: `RanaDataItemProvider` + `RanaRootDataItem`
- **Estimate:** ~70 lines
- **Files:** `rana_qgis_plugin/data_items/rana_item.py` (new), `rana_qgis_plugin/rana_qgis_plugin.py`
- **Description:** Browser root item with login/logout/switch_tenant flow, prompt dialogs,
  tooltip, session restore on startup. `RanaDataItemProvider` in plugin entrypoint.
  `login`, `prompt_tenant`, `prompt_provider`, `status_tooltip` moved here from `auth.py`.
- **Depends on:** Task 3b

#### Task 5: Tenant switch + rollback
- **Estimate:** ~55 lines
- **Files:** `rana_qgis_plugin/data_items/rana_item.py`
- **Description:** `switch_tenant()` with radio button dialog, snapshot/rollback on failure.
  Switch tenant action shown only when ≥2 tenants available. Tenant list cached on item
  after login and cleared on logout.
- **Depends on:** Task 4

#### Task 6: `RanaSettingsDialog`
- **Estimate:** ~45 lines
- **Files:** `rana_qgis_plugin/widgets/settings_dialog.py` (new)
- **Description:** Minimal `QDialog` for backend URL only. On save: clears tenant + credentials
  if URL changed; triggers re-login if was authenticated. Dialog stores only, caller handles
  auth lifecycle.
- **Depends on:** Task 2

---

### Integration & Polish

#### Task 7: Plugin entrypoint wiring + legacy removal
- **Estimate:** ~60 lines
- **Files:** `rana_qgis_plugin/rana_qgis_plugin.py`, any legacy entrypoint wires
- **Description:**
  - Remove legacy menu/toolbar auth UI from `initGui()` and `unload()`.
  - Clean up legacy auth module imports from all entrypoint files.
- **Depends on:** Tasks 5, 6

---

## Notes

- `auth.py` is pure credential logic: `is_authenticated`, `clear_credentials`,
  `clear_credentials_if_url_changed`, `fetch_identity_providers`, `create_oauth2_config`,
  `active_tenant`. No Qt, no UI.
- `RanaRootDataItem` owns all UI flow: login, logout, switch_tenant, prompts, tooltip.
- `RanaSettingsDialog` stores only; caller handles auth lifecycle.
- No imports from `rana_qgis_plugin.legacy.*` in new modules (FR-012).

## Progress

- [x] Task 0: Developer documentation — login/logout flow
- [x] Task 1: Auth state model + `is_authenticated()` (TDD)
- [x] Task 2: Logout + URL-change-forces-logout (TDD)
- [x] Task 3a: Login — tenant resolution + identity provider fetch (TDD)
- [x] Task 3b: Login — OAuth2 config creation + auth completion (TDD)
- [x] Task 4: `RanaDataItemProvider` + `RanaRootDataItem`
- [x] Task 5: Tenant switch + rollback
- [x] Task 6: `RanaSettingsDialog`
- [x] Task 7: Plugin entrypoint wiring + legacy removal
