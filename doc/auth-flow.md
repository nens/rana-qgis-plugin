# Rana authentication — developer flow

This living document describes the auth lifecycle for the Rana Browser entrypoint. Update this file whenever auth behaviour changes.

## Architecture note

Auth logic lives in `rana_qgis_plugin/auth.py` as a module of plain functions. All persistent state is stored in `QgsSettings` and `QgsAuthManager` — there is no in-memory state object.

## Login: new user (first time or after logout)

The user has no stored tenant or authcfg. They must pick a tenant and authentication method.

```mermaid
sequenceDiagram
    participant User
    participant Browser as RanaRootDataItem
    participant Auth as auth module
    participant AuthMgr as QgsAuthManager

    Note over User,Browser: Triggered from the Rana tree context menu (right-click -> "Login")
    User->>Browser: choose Login (context menu)
    Browser->>Auth: login()
    Auth->>User: prompt: choose tenant
    User-->>Auth: tenant_id
    Auth->>Auth: fetch_identity_providers()
    Auth-->>User: prompt: choose provider (SSO / password)
    User-->>Auth: selected provider
    Auth->>AuthMgr: create OAuth2 config (persistToken=true)
    AuthMgr-->>Auth: authcfg_id
    Auth->>Auth: persist tenant + authcfg_id to settings
    Auth->>Browser: refresh UI
```

## Login: returning user (after restart)

Tenant and authcfg ID are already stored. QGIS Auth Manager still holds the token (persisted). No user interaction needed.

```mermaid
sequenceDiagram
    participant Browser as RanaRootDataItem
    participant Auth as auth module
    participant AuthMgr as QgsAuthManager

    Browser->>Auth: is_authenticated()
    Auth->>Auth: check Rana/base_url set
    Auth->>Auth: check Rana/authcfg ID in settings
    Auth->>AuthMgr: resolve authcfg_id
    AuthMgr-->>Auth: config found
    Auth-->>Browser: True — UI shows authenticated actions

    Note over Browser,Auth: On startup RanaRootDataItem.__init__ calls _restore_session()
    Browser->>Auth: _restore_session()
    Auth->>Auth: get_user_info()
    Auth-->>Auth: user info returned
    Auth->>Auth: get_user_tenants()
    Auth-->>Auth: tenant list returned
    Auth->>Browser: silently populate UI (no prompts)
```

Key notes:
- On restart, if all three conditions pass, the user is immediately signed in — no prompts shown.
- __init__ calls _restore_session() which fetches user info and the cached tenant list (get_user_info(), get_user_tenants()) so the UI is populated silently.
- If the authcfg ID is in settings but not found in `QgsAuthManager` (stale), it is removed from settings automatically and the user is treated as signed out (see `is_authenticated()` contract below).
- OAuth2 config creation writes secrets/tokens into QGIS Auth Manager; only the config ID is persisted to Rana settings.

## Logout

```mermaid
sequenceDiagram
    participant User
    participant Browser as RanaRootDataItem
    participant Auth as auth module
    participant AuthMgr as QgsAuthManager

    User->>Browser: choose Logout
    Browser->>Browser: logout()
    Browser->>Auth: clear_credentials()
    Auth->>AuthMgr: remove authcfg from QgsAuthManager
    Auth->>Auth: clear Rana/authcfg from settings
    Auth-->>Browser: done — UI shows logged-out actions
```

RanaRootDataItem.logout() calls auth.clear_credentials() which removes the QGIS authcfg and the stored settings pointer.

## Tenant switch (with rollback)

```mermaid
sequenceDiagram
    participant User
    participant Browser as RanaRootDataItem
    participant Auth as auth module

    User->>Browser: choose Switch tenant
    Browser->>Auth: switch_tenant()
    Auth->>Auth: snapshot current tenant + authcfg_id
    Auth->>User: prompt_switch_tenant()  
    Note right of Auth: shows radio dialog of cached tenants (self._tenants)
    User-->>Auth: new_tenant_id or CANCEL
    alt cancelled or same tenant
        Auth-->>Browser: return early (no change)
    else new tenant selected
        Auth->>Auth: logout()  
        Auth->>Auth: login(start_tenant_id=new_tenant)  
        alt success
            Auth->>Auth: persist new tenant + authcfg_id to settings
            Auth->>Browser: refresh UI
        else failure
            Auth->>Auth: restore snapshot (authcfg_id + tenant) to settings
            Auth->>Browser: show error message
        end
    end
```

Notes:
- The tenant list presented in prompt_switch_tenant() is the cached self._tenants fetched during login/restore — it is not fetched fresh during switch_tenant().
- Flow order: prompt happens before logout; logout only occurs after a new tenant is chosen. If the user cancels or re-selects the current tenant, no logout occurs.
- Rollback rule: if re-login for the new tenant fails at any step, the prior authcfg ID and tenant MUST be restored in settings so the user is not left logged-out.

## is_authenticated() contract

`is_authenticated()` MUST return `True` iff ALL of the following are true:
1. A backend URL is configured in settings (`Rana/base_url`), AND
2. A stored authcfg ID is present in settings (`Rana/authcfg`), AND
3. That authcfg ID resolves to a config in `QgsAuthManager`.

If an authcfg ID is present in settings but does NOT resolve in `QgsAuthManager` (stale pointer), the implementation MUST automatically remove the stored ID from settings. No network probe is required — resolution against `QgsAuthManager` is sufficient.

## Security: URL-change-forces-logout

In the Settings dialog open_settings() workflow the following happens:

1. Dialog opens
2. On Accepted and dlg.url_changed() is True:
   - Remove stored tenant entry (`RANA_TENANT_ENTRY`)
   - Call `clear_credentials()` (removes authcfg from QGIS Auth Manager)
   - Reset `_tenants = None`
   - Update tooltip and refresh UI
   - If the user WAS authenticated before opening settings: automatically trigger `self.login()` to start a fresh login flow

This is done explicitly in open_settings(), not via an external settings listener.

## Fetching Cognito client IDs from the backend (`update_auth_settings`)

Different backend deployments (e.g. staging vs. production) run their own Cognito user pools and therefore have different client IDs. The plugin must use the client IDs that match the configured backend URL; hardcoding them is not possible.

When the user saves a new backend URL in the Settings dialog, `update_auth_settings(new_url)` is called before the dialog is accepted:

1. Stores the new URL in settings.
2. Calls `GET <new_url>/api/frontend-settings` synchronously.
3. On success: stores `default_client_id` (used for SSO flows) and `native_client_id` (used for username/password flows) in `QgsSettings`.
4. On failure: reverts the URL to the previous value and returns `False` — the dialog shows an error and stays open.

These stored client IDs are then read by `create_oauth2_config()` when building the OAuth2 config for a login attempt. This means `update_auth_settings` must succeed before any login against a new backend is possible.

## When to update this document

Any change to login sequences, the `is_authenticated()` contract, rollback behaviour, or the URL-change rule MUST be reflected here before merging.
