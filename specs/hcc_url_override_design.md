# Feature Specification: HCC URL Override Configuration

**Created**: 2026-04-23  
**Status**: Planned  
**Input**: User description: "Add a way to change the url used for the hcc (utils.generic.get_threedi_api). By default it should be retrieved via get_frontend_settings, but if it's defined the QgsSettings (hcc_url) that value should be used instead."

## User Scenarios & Testing

### User Story 1 - Power User Overrides 3Di API URL (Priority: P1)

A power user or developer needs to point the plugin to an alternative 3Di API instance (e.g., development server, alternative deployment) without waiting for backend configuration changes or affecting other users of the same Rana deployment.

**Why this priority**: This is the core functionality requested. It enables advanced deployment scenarios and development workflows.

**Independent Test**: User can set `hcc_url` in QGIS config file, and the plugin uses that URL instead of the one from `get_frontend_settings()` when creating 3Di API clients.

**Acceptance Scenarios**:

1. **Given** `hcc_url` is not set in QgsSettings, **When** `get_threedi_api()` is called, **Then** it uses the `hcc_url` from `get_frontend_settings()`
2. **Given** `hcc_url` is set to a custom value in QgsSettings, **When** `get_threedi_api()` is called, **Then** it uses the QgsSettings value instead of `get_frontend_settings()`
3. **Given** `hcc_url` is set in QgsSettings to an invalid URL, **When** `get_threedi_api()` is called, **Then** the function attempts to use it (no validation — power user responsibility)

---

### User Story 2 - Advanced Settings Visibility in Settings Dialog (Priority: P2)

Advanced configuration settings should be discoverable and visible to users who have configured them, without cluttering the UI for regular users.

**Why this priority**: Secondary UX improvement that helps users see what advanced settings are active without adding noise to the default UI.

**Independent Test**: Settings Dialog displays an "Advanced" section showing `hcc_url` and `use_plugin_excepthook` only when at least one has a value.

**Acceptance Scenarios**:

1. **Given** no advanced settings are configured, **When** Settings Dialog is opened, **Then** no "Advanced" section is displayed
2. **Given** `hcc_url` is set in QgsSettings, **When** Settings Dialog is opened, **Then** an "Advanced" section appears showing `hcc_url` with its value
3. **Given** both `hcc_url` and `use_plugin_excepthook` are set, **When** Settings Dialog is opened, **Then** "Advanced" section displays both settings (read-only)

---

### Edge Cases

- What happens when `hcc_url` is set but invalid? → Function uses it anyway; power user responsibility
- What happens when `get_frontend_settings()` fails but `hcc_url` override is set? → Uses override; allows continued operation
- What if user sets empty string for `hcc_url`? → Treated as empty override; falls back to `get_frontend_settings()`

## Requirements

### Functional Requirements

- **FR-001**: System MUST check QgsSettings for `hcc_url` key before using `get_frontend_settings()["hcc_url"]`
- **FR-002**: System MUST return the QgsSettings `hcc_url` value if it exists, otherwise return the value from `get_frontend_settings()`
- **FR-003**: System MUST display advanced settings in Settings Dialog only when they have configured values
- **FR-004**: Advanced settings display MUST be read-only; editing must occur via config file only
- **FR-005**: System MUST support `hcc_url` and `use_plugin_excepthook` as trackable advanced settings

### Key Entities

- **hcc_url Setting**: Stores the override URL for the 3Di API endpoint. Key: `"Rana/hcc_url"` in QgsSettings. Type: string. Optional.
- **Advanced Settings Display**: Read-only UI component in Settings Dialog that shows active advanced configuration.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Power users can override 3Di API URL via QgsSettings without modifying source code
- **SC-002**: Settings Dialog correctly hides Advanced section when no advanced settings are configured
- **SC-003**: Settings Dialog correctly displays all configured advanced settings when they exist
- **SC-004**: `get_threedi_api()` function correctly prioritizes QgsSettings override over frontend_settings

---

## Design Details

### Architecture Overview

```
User sets hcc_url in QgsSettings config file
         ↓
get_threedi_api() called in utils/generic.py
         ↓
Calls get_hcc_url_override() from utils/settings.py
         ↓
Returns value or None
         ↓
If value exists: Use it
If None: Fall back to frontend_settings["hcc_url"]
         ↓
Create and return ThreediApi client
```

### Components & Changes

#### 1. **utils/settings.py**
- Add function `get_hcc_url_override() -> Optional[str]`:
  - Retrieves the value from QgsSettings using key `"Rana/hcc_url"`
  - Returns None if not set
  - Returns the string value if set
  
- Add function `get_advanced_settings() -> dict`:
  - Returns a dictionary of advanced settings that have values
  - Format: `{"hcc_url": "<value>"}`
  - Only includes keys where values are non-empty/non-None
  - Extensible for future advanced settings

#### 2. **utils/generic.py**
- Modify `get_threedi_api()` function:
  - Before using `frontend_settings["hcc_url"]`, check `get_hcc_url_override()`
  - If override exists and is non-empty, use it
  - Otherwise use `frontend_settings["hcc_url"]` (current behavior)

#### 3. **widgets/settings_dialog.py**
- Add "Advanced" section at the bottom of the Settings Dialog
- Call `get_advanced_settings()` during dialog initialization
- Only create and display Advanced section if dictionary is non-empty
- Render each advanced setting as a read-only label pair: setting name + value
- Display format: Clean, minimal labels (e.g., "hcc_url: https://...")

### Data Flow

```
Settings Dialog Initialization:
  1. Dialog opens
  2. Call get_advanced_settings()
  3. If returned dict is empty → Don't create Advanced section
  4. If dict has items → Create section with header "Advanced"
  5. For each item, display as read-only: "key: value"

3Di API Client Creation:
  1. get_threedi_api() called
  2. Call get_hcc_url_override()
  3. If result is not None/empty → Use it
  4. Else → Use frontend_settings["hcc_url"]
  5. Pass resolved URL to get_api_client_with_personal_api_token()
```

### Testing Strategy

**Unit Tests** (to be written):

1. **test_get_hcc_url_override()**
   - When `Rana/hcc_url` is not set, returns None
   - When `Rana/hcc_url` is set, returns the value
   - When `Rana/hcc_url` is empty string, returns empty string

2. **test_get_advanced_settings()**
   - When no advanced settings are set, returns empty dict
   - When `hcc_url` is set, includes it in returned dict
   - When `use_plugin_excepthook` is set, includes it in returned dict
   - When both are set, includes both in returned dict

3. **test_get_threedi_api_uses_override()**
   - When `hcc_url` override is set, uses that URL for API client
   - When `hcc_url` override is None, uses frontend_settings value
   - When `hcc_url` override is empty string, falls back to frontend_settings

**Manual Testing**:

1. Set `hcc_url` in QGIS config file, verify `get_threedi_api()` uses it
2. Unset `hcc_url`, verify normal behavior is restored
3. Open Settings Dialog with no advanced settings → verify no Advanced section visible
4. Set `hcc_url` in config, reopen Settings Dialog → verify Advanced section appears with the value
5. Set both `hcc_url` and `use_plugin_excepthook` → verify both appear in Advanced section

### Configuration Example

Users would add this to their QGIS settings file (location varies by OS):

```
# QGIS settings file (e.g., ~/.config/QGIS/QGIS3.ini on Linux)
[Rana]
base_url=https://www.ranawaterintelligence.com
hcc_url=https://dev-3di-api.example.com
```

---

## Implementation Notes

- **No URL validation**: Power users are responsible for valid URLs. The function will fail at runtime if the URL is invalid.
- **No UI control for editing**: Users must edit the config file directly. Settings Dialog is read-only display only.
- **Extensible**: `get_advanced_settings()` makes it easy to add more advanced settings in future without modifying dialog logic.
- **Backwards compatible**: Existing deployments without this setting continue to work unchanged.

---

## Open Questions

None — design is complete and ready for implementation.
