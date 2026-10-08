---
feature: rana-qgsdataitemprovider-auth-bootstrap
status: complete
created: 2026-07-29
decisions:
  - 20260729-1536-datasource-first-auth-entrypoint
  - 20260729-1537-rana-root-auth-interaction-model
  - 20260729-1538-tenant-lifecycle-and-relogin
  - 20260729-1539-settings-scope-backend-url-only
  - 20260729-1540-auth-success-visibility
---

# Rana QgsDataItemProvider Auth Bootstrap Design

## Overview

This feature introduces a Rana `QgsDataItemProvider`-driven entry point for authentication and tenant-aware browsing. It replaces menu-first auth behavior with datasource-first behavior while preserving core legacy flow semantics: OAuth2 config in QGIS auth store, tenant persistence in settings, login/logout actions, and tenant switching with re-authentication.

Legacy code is used only as a behavior reference (`legacy/auth.py`, `legacy/rana_qgis_plugin.py`). Any reused logic must be copied into new typed modules, never imported from `legacy`.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Login from Browser root (Priority: P1)

As a Rana user, I can log in directly from the Rana Browser datasource root so I can access Rana data without using a top plugin menu.

**Why this priority**: Authentication is the hard blocker for all datasource access.

**Independent Test**: In a fresh QGIS session with no active auth config, double-clicking the Rana root item starts login, and successful login unlocks authenticated datasource behavior.

**Acceptance Scenarios**:

1. **Given** Rana root is visible and user is logged out, **When** the user double-clicks Rana root, **Then** login flow starts.
2. **Given** login succeeds, **When** auth flow completes, **Then** authenticated actions are visible and datasource can refresh authenticated children.

---

### User Story 2 - Logout and tenant switch (Priority: P1)

As a logged-in user, I can logout or switch tenant from the Rana root context menu so I can control active session context.

**Why this priority**: Session lifecycle and tenant control are explicit scope requirements.

**Independent Test**: While logged in, context menu exposes Logout and Switch tenant; logout clears session; switch tenant triggers re-login.

**Acceptance Scenarios**:

1. **Given** user is logged in, **When** user selects Logout, **Then** auth config is removed, tenant state is handled per policy, and UI returns to logged-out actions.
2. **Given** user is logged in, **When** user selects Switch tenant and picks a new tenant, **Then** current auth is invalidated and login flow is re-run for the new tenant.

---

### User Story 3 - Tenant memory and first-time prompt (Priority: P2)

As a returning user, I want tenant to be remembered so I do not re-enter tenant every login, while first-time users are prompted when no tenant exists.

**Why this priority**: Preserves known legacy behavior and reduces friction.

**Independent Test**: Tenant is asked only when missing; once stored, subsequent login uses stored tenant automatically unless tenant switch is requested while logged in.

**Acceptance Scenarios**:

1. **Given** no stored tenant, **When** login starts, **Then** tenant prompt is shown and result is persisted.
2. **Given** stored tenant exists, **When** login starts, **Then** tenant prompt is skipped.

---

### User Story 4 - Auth status visibility (Priority: P2)

As a user, I can quickly see whether login succeeded from Browser interactions.

**Why this priority**: Explicit requirement to surface success state.

**Independent Test**: After login/logout/failure, Rana root tooltip and message bar feedback reflect current auth state.

**Acceptance Scenarios**:

1. **Given** user is logged out, **When** hovering Rana root, **Then** tooltip indicates user is not logged in and can double-click to login.
2. **Given** login succeeds, **When** user hovers Rana root, **Then** tooltip shows signed-in user/tenant context.

---

## Edge Cases

- OAuth config ID exists in settings but no longer exists in `QgsAuthManager` (stale pointer): treat as logged out and recover on login.
- Login canceled at tenant prompt or provider-selection step: remain logged out without partial state mutation.
- Tenant switch re-login fails: previous authenticated state must not remain active.
- Identity providers endpoint fails: show user-visible error and keep datasource in logged-out state.
- Backend URL changed via settings while logged in: require explicit re-login path before next authenticated fetch.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST register a Rana `QgsDataItemProvider` entry point that is always visible in Browser.
- **FR-002**: System MUST initiate login flow when the Rana root item is double-clicked while logged out.
- **FR-003**: System MUST expose context menu actions by auth state:
  - logged out: `Login`, `Settings`
  - logged in: `Logout`, `Settings`
  - `Switch tenant` action MUST be shown only when the user has access to two or more tenants; if only one tenant is available the action MUST be hidden entirely (do not show disabled).
- **FR-004**: System MUST NOT expose tenant-change action while logged out.
- **FR-005**: System MUST persist auth configuration ID in settings and OAuth2 secrets/tokens in QGIS Auth Manager.
- **FR-006**: System MUST persist tenant ID and reuse it on future login attempts.
- **FR-007**: System MUST prompt for tenant only when no tenant is stored.
- **FR-008**: System MUST prompt sign-in method each login attempt (no remembered provider choice).
- **FR-009**: System MUST enforce re-authentication when switching tenant.
- **FR-010**: System MUST provide auth success/failure visibility via tooltip and message bar feedback.
- **FR-011**: System MUST provide a Settings dialog with backend URL editing only for this increment.
- **FR-012**: New implementation MUST not import from `rana_qgis_plugin.legacy.*`; any reused legacy behavior is copied into new typed modules.
- **FR-013**: New code MUST pass project mypy checks and pre-commit validation.
 - **FR-014**: Security: On backend URL change the system MUST immediately invalidate/remove the stored authcfg from `QgsAuthManager` and transition auth state to logged-out. No authenticated request must be sent to the new URL using old credentials; the user MUST re-authenticate for the new backend.
 - **FR-015**: `Switch tenant` visibility: UI must only show the `Switch tenant` action when >=2 tenants are available for the current identity; otherwise it must be omitted.

### Key Entities *(include if feature involves data)*

- **TenantState**: Persisted tenant ID (`Rana/tenant`) plus runtime tenant list for switch action.
- **RanaRootDataItem**: Browser root item with dynamic actions and tooltip based on auth state.

## Components

### `rana_qgis_plugin/auth` module (new)

Module of functions (no class) that encapsulates:
- auth config lookup/validation (`is_authenticated`)
- login bootstrap and OAuth2 setup
- tenant persistence and tenant switch workflow
- logout and stale authcfg cleanup

All state is persisted in `QgsSettings` and `QgsAuthManager`; there is no in-memory state object.

### RanaDataItemProvider + RanaRootDataItem (new)

Browser-facing component that:
- always exposes Rana root item
- triggers login on double-click when logged out
- exposes state-aware context actions
- updates tooltip and refreshes children on auth state changes

### RanaAuthSettingsDialog (new or adapted)

Minimal dialog for backend URL only in this increment.

## Integration

How Rana is wired into the active plugin runtime and migration notes:

- The Rana data provider is registered with QGIS during plugin startup: QgsApplication.dataItemProviderRegistry().addProvider(RanaDataItemProvider(...)) is invoked from plugin initGui().
- Legacy menu/toolbar authentication UI is removed in the same increment: this is a full replacement (not side-by-side) to avoid dual-entry confusion.
- Legacy auth module imports (e.g. `legacy/auth.py`) are cleaned up in the same increment; any reused logic must be copied into the new typed modules rather than imported.

## Data Model

- `QgsSettings[Rana/authcfg] -> str | None`
- `QgsSettings[Rana/tenant] -> str | None`
- `QgsSettings[Rana/base_url] -> str`
- `QgsAuthManager[authcfg_id] -> OAuth2 config (persistToken=True)`

## API/Interface

Expected internal functions (typed), all in `rana_qgis_plugin/auth.py`:
- `is_authenticated() -> bool`
- Contract: `is_authenticated()` MUST return true iff all of the following are true:
  1. A backend URL is set in QGIS settings (`Rana/base_url`), AND
  2. A stored authcfg ID is present in settings (`Rana/authcfg`), AND
  3. That authcfg ID exists in `QgsAuthManager` (i.e. the auth config can be resolved).

  If the authcfg ID is present in settings but does not exist in `QgsAuthManager`, the implementation MUST treat this as a stale authcfg: automatically remove the stored ID from settings. An optional asynchronous lightweight user-info probe (for example when opening the Browser panel) is a future enhancement and is NOT required for this increment.
- `login(start_tenant_id: str | None = None) -> bool`
- `logout() -> bool`
- `switch_tenant() -> bool`
- `active_tenant() -> str | None`
- `status_tooltip() -> str`

Browser item interaction points:
- `handleDoubleClick()` (logged-out triggers login)
- `actions(parent)` (dynamic action list based on auth state)

## Manual Testing Paths

- Browser panel → Rana root visible while logged out
- Rana root double-click while logged out → login flow
- Context menu (logged out) → Login, Settings only
- Context menu (logged in) → Logout, Switch tenant, Settings
- Switch tenant → re-login required and result reflected
- Tooltip + message bar feedback after login/logout/error
- Settings dialog backend URL update behavior

## Testing

Unit test matrix (auth state logic). All unit tests should mock `QgsAuthManager` and QGIS settings; no real network/API access is required.

- is_authenticated() variations:
  - valid authcfg: settings contain backend URL and authcfg ID, and QgsAuthManager resolves the ID -> expect True (unit test)
  - stale authcfg: settings contain authcfg ID but QgsAuthManager does not resolve it -> expect automatic cleanup, transition to logged-out state (unit test)
  - no authcfg ID in settings -> expect False (unit test)
  - no backend URL set -> expect False (unit test)

- Logout: calling logout must remove authcfg from both QgsAuthManager and settings and set auth state to logged-out (unit test)

- URL change: changing the backend URL must trigger logout and removal/invalidation of the stored authcfg, leaving the system logged-out (unit test)

- Tenant switch rollback: if tenant switch/re-login fails, the previous tenant/auth state must be restored (unit test)

- Auth dialog cancelled: cancelling the auth dialog at any step must leave the system logged-out with no partial state persisted (unit test)

- Network failure during login: simulated network error during login must leave the system logged-out and surface a user-visible error (unit test)

Notes: UI-driven flows (auth dialog UI, provider selection dialogs, and real network interactions) remain covered via the existing manual test paths only.

## Open Questions

- Should backend URL changes while logged in force immediate logout or deferred re-auth on next action?
- Do we need explicit stale-authcfg auto-cleanup on plugin startup, or only on first auth interaction?
- Should the datasource expose a lightweight child placeholder when logged out, or remain non-fertile until login?

## Success Criteria *(mandatory)*

### Measurable Outcomes

 - **SC-001 (revised)**: For each defined scenario below the passing criterion is: application does not crash + the user sees a visible, descriptive message + the auth state is correctly set or rolled back. Each scenario indicates whether covered by unit tests or manual tests.

  Scenarios:
  1. Stale authcfg on plugin load
     - Expected: plugin detects stale authcfg, performs automatic cleanup, transitions to logged-out, and shows a user-visible message.
     - Covered: unit test

  2. User cancels login dialog
     - Expected: no credentials or partial auth state are stored; state remains logged-out; user-visible message or no-op indicator.
     - Covered: unit test (state) + manual test for UI flow

  3. Network error during login
     - Expected: login aborts, state remains logged-out, and a user-visible error is shown.
     - Covered: unit test (simulated network failure) + manual

  4. Identity provider fetch failure
     - Expected: user-visible error and remain logged-out; no partial auth state persisted.
     - Covered: manual test (network/provider integration)

  5. Tenant switch failure (rollback)
     - Expected: previous tenant/auth state restored; user-visible error shown; no partial tenant change persisted.
     - Covered: unit test

  6. Backend URL change while logged in
     - Expected: immediate invalidation/removal of stored authcfg, transition to logged-out, and user-visible notification that re-authentication is required.
     - Covered: unit test

  7. Successful login and datasource population
     - Expected: no crash; user sees success message; authenticated actions visible; datasource children refresh/populate as expected.
     - Covered: manual test for full integration (UI + network)
- **SC-002**: After successful login, authenticated context actions are available within one Browser refresh cycle.
- **SC-003**: In repeated sessions, tenant prompt appears only when no tenant is stored.
- **SC-004**: Switching tenant always triggers re-authentication before authenticated datasource requests continue.
