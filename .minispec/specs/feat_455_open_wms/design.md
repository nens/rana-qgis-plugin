---
feature: feat_455_open_wms
status: planned
created: 2026-09-21
decisions:
  - 20260921-1800-wms-module-level-layer-opening
  - 20260921-1801-wms-shared-single-and-batch-flow
  - 20260921-1802-wms-selection-and-folder-scope
---

# Open WMS for Scenarios Design

## Overview

Task 455 has already implemented downloading and opening scenario results. This
feature implements the remaining Open WMS action for scenario files.

Users can open WMS layers for one scenario or for a multi-selection containing
only scenarios. Folder-level Open WMS is intentionally out of scope for now.
The WMS flow does not download files, show a result-selection dialog, or open
Results Analysis.

## User Stories

- As a user, I want to open the WMS representation of one scenario in QGIS so
  that I can view its published layers without downloading results.
- As a user, I want to open WMS layers for several selected scenarios at once
  so that I can compare them efficiently.

## Components

### Module-level WMS layer opening

Add `open_rana_wms` to
`rana_qgis_plugin/layer_management/layer_manager.py`. It follows the current
module-level layer-opening functions and uses the existing Rana group helpers.
It creates one `QgsRasterLayer` per descriptor layer using the WMS URI
parameters used by the legacy implementation:

- `layers`: descriptor layer code
- `styles`: empty string
- `format`: `image/png`
- `url`: descriptor WMS link URL
- `authcfg`: current Rana authentication configuration

The Loader supplies a WMS-specific group path: the project/files path followed
by the scenario path and a final `wms` segment. For a scenario with ID
`path/to/scenario`, layers therefore appear at:

```text
<project>/files/path/to/scenario/wms/<layer>
```

The function adds valid layers to the supplied group and returns the layers
that were added. WMS layers are deliberately not tagged with `RanaLayerRef`,
because they do not represent local files and do not need dirty tracking.

The obsolete `LayerManager`, `FileLayerManager`, and
`PublicationLayerManager` class hierarchy should be removed once a final
reference check confirms that active code does not use it. The legacy plugin is
reference-only and is not loaded by the active `classFactory` entry point.

### Scenario WMS request

Add `OpenScenarioWmsRequest(project, file_item)` to `utils/data_models.py`.
It is separate from `OpenScenarioRequest`, which represents the result
download/open flow.

### Loader WMS flow

Add dedicated `Loader.open_scenario_wms(request)` and
`Loader.open_scenario_wms_batch(requests)` entry points. WMS requests do not
go through the general `open_items()` dispatcher. The single-scenario method
fetches the descriptor on the main thread, finds the `rel == "wms"` link and
`meta.layers`, and delegates layer creation to `open_rana_wms`. The batch
method iterates requests and invokes the same per-scenario helper once per
scenario. Missing descriptors, WMS links, or layers produce a clear
message-bar result and do not raise an unhandled exception.

Single and batch operations share the same per-scenario helper so descriptor
fetching, validation, layer creation, and error handling are not duplicated.
Batch processing is synchronous; there is no `QgsTask` because the operation
only performs metadata retrieval and layer construction.

### Context-menu actions

Wire `FileAction.OPEN_WMS` in `RanaFileDataItem.actions()` to the new single
scenario request. Double-click behavior remains unchanged: it continues to
open the scenario result flow.

Add `OPEN_WMS` to the multi-select action whitelist. The existing action
intersection logic ensures that the action is available only when every
selected item exposes it; because only scenario files expose it, mixed file
selections do not receive the action.

## Data Model

```python
@dataclass(frozen=True)
class OpenScenarioWmsRequest:
    project: dict
    file_item: dict
```

The descriptor is fetched when the request is executed. Its relevant shape is:

```python
{
    "links": [{"rel": "wms", "href": "..."}],
    "meta": {
        "layers": [
            {"code": "...", "name": "...", "label": "..."},
        ],
    },
}
```

## API/Interface

Planned interfaces:

```python
def open_rana_wms(
    descriptor: dict,
    layers: list[dict],
    parents: list[str],  # includes the final ``wms`` group segment
    project_id: str,
) -> list[QgsRasterLayer]: ...

def Loader.open_scenario_wms(
    self, request: OpenScenarioWmsRequest
) -> None: ...

def Loader.open_scenario_wms_batch(
    self, requests: list[OpenScenarioWmsRequest]
) -> None: ...
```

The exact private helper name used to share single and batch processing may be
chosen during implementation, but both public flows must delegate to the same
per-scenario behavior.

## Error Handling

- Missing or invalid descriptors: report the affected scenario and continue
  processing other batch items.
- Missing WMS link: report that WMS is unavailable for the affected scenario.
- Empty descriptor layer list: report that the file has no layers.
- Invalid QGIS WMS layers: do not add them; report the affected file if no
  layer could be opened.

## Scope Boundaries

This design does not change:

- scenario result downloading or Results Analysis integration;
- scenario double-click behavior;
- folder-level Open WMS;
- dirty tracking or Rana references for WMS layers;
- the legacy plugin implementation;
- background task infrastructure for WMS metadata retrieval.

## Open Questions

- During implementation, verify all references to the old layer-manager class
  hierarchy before deleting it. Remove only code confirmed to be obsolete.
- Confirm the final user-facing wording for single-file and batch message-bar
  feedback.
