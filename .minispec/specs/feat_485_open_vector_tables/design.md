---
feature: feat_485_open_vector_tables
status: draft
created: 2026-09-29
decisions: []
---

# Open Vector Tables Design

## Overview

Extend the Rana QGIS Browser and vector-file opening flow to support
geometryless tables in addition to spatial vector layers.

The feature has three goals:

1. Show tables when a Rana vector file is expanded in the Browser.
2. Allow an individual table to be opened, including selections containing a
   mixture of layers and tables.
3. Open all spatial layers and supported tables when a vector file is opened.

The design extends the existing vector-file flow. Tables are not introduced
as a new top-level Rana file type.

## Current API/schema observation

The `file_descriptor_retrieve` response is confusing because layer metadata is
exposed in more than one place, while table metadata is only present in the
vector metadata.

The current code uses the descriptor-level `layers` field when expanding a
Browser vector file (`file_item.py`), while the layer manager uses
`descriptor["meta"]["layers"]` in its opening path. This discrepancy must be
resolved or explicitly handled during implementation.

The API research found the following vector metadata shape:

```python
descriptor["meta"]["layers"] = [
    {
        "id": "layer-child-id",
        "name": "roads",
        "type": "Polygon",
    },
]

descriptor["meta"]["tables"] = {
    "<provider-defined-key>": {
        "layer_id": "parent-layer-id",
        "table_id": "table-child-id",
        "columns": {...},
    },
}
```

The exact meaning of the outer `meta["tables"]` map key is not yet
confirmed. In particular, it is not yet known whether that key is the
canonical local GeoPackage table name. Table records do not currently expose
a documented table-level `name`, `label`, or `type` field.

This uncertainty is intentionally recorded as an open question rather than
being hidden behind an assumed data model.

## User Scenarios & Testing

### User Story 1 - Browse vector tables (Priority: P1)

As a user, I want tables to appear when I expand a Rana vector file so that I
can choose a table just as I can choose a spatial layer.

**Independent Test**: Expand a vector file whose descriptor contains both
layers and tables and verify that both kinds of children appear with their
correct names and item types.

**Acceptance Scenarios**:

1. **Given** a vector descriptor with spatial layers and tables, **when** the
   file is expanded, **then** spatial layer and table children are shown.
2. **Given** a vector descriptor without tables, **when** the file is
   expanded, **then** existing layer expansion is unchanged.
3. **Given** descriptor fetch failure, **when** the file is expanded, **then**
   the existing error-item behavior is preserved.

### User Story 2 - Open selected vector children (Priority: P1)

As a user, I want to open one or more selected layers and tables so that I
can work with only the vector-file contents I need.

**Independent Test**: Select one layer and one table from the same vector
file, choose Open in QGIS, and verify that both are opened after one file
download.

**Acceptance Scenarios**:

1. **Given** a selected layer child, **when** it is opened, **then** only that
   layer is added to QGIS.
2. **Given** a selected table child, **when** it is opened, **then** only that
   table is added to QGIS as a geometryless vector layer.
3. **Given** selected layers and tables from one file, **when** they are
   opened together, **then** the file is downloaded once and every selected
   child is opened.
4. **Given** selected children from different files, **when** they are opened
   together, **then** each file is downloaded once and its requested children
   are opened.

### User Story 3 - Open a complete vector file (Priority: P1)

As a user, I want opening a vector file to include all supported spatial
layers and tables, rather than silently omitting tables.

**Independent Test**: Open a downloaded GeoPackage containing spatial layers
and geometryless tables and verify that all descriptor-listed children are
present in the QGIS layer tree.

**Acceptance Scenarios**:

1. **Given** a vector file with descriptor-listed layers and tables, **when**
   the file is opened, **then** all available listed layers and tables are
   added to the existing Rana group hierarchy.
2. **Given** a descriptor-listed table that is absent from the downloaded
   file, **when** the file is opened, **then** the missing table is reported
   and the remaining valid children are still opened.
3. **Given** geometryless local sublayers that are not listed in the
   descriptor, **when** the file is opened, **then** those unlisted/internal
   tables are not opened.

## Design Decisions So Far

### Dedicated Browser item for tables

Tables will be represented by a new `RanaTableDataItem`, separate from
`RanaLayerDataItem`.

This keeps geometry-bearing layers and geometryless tables explicit in the
Browser model and allows their opening behavior to be selected by type.

### Reuse the existing icon mechanism

Table items will use the same path as spatial layer items:

```text
table metadata/type
    -> get_file_icon_name(...)
    -> get_icon_from_theme(...)
```

The implementation should add the appropriate table mapping to the existing
generic icon map and use a QGIS-native theme icon. No separate icon helper or
bundled plugin asset is planned unless QGIS 4.x has no suitable theme icon.

### Unified selected-child request

Selected layers and tables will use one request type named
`OpenVectorChildrenRequest`, rather than separate layer and table request
pipelines.

The request represents one parent vector file and a collection of selected
children. It permits one download per file and naturally supports mixed
layer/table selections.

### Separate request reference classes

The request children will be represented by two immutable value objects:

```python
@dataclass(frozen=True)
class VectorLayerRef:
    name: str
    id: str


@dataclass(frozen=True)
class VectorTableRef:
    name: str
    id: str
```

The request contains a tuple of either type:

```python
children: tuple[VectorLayerRef | VectorTableRef, ...]
```

The concrete Python class identifies the opening behavior. The classes are
request-time selectors, not persistent QGIS metadata objects.

- `name` identifies the local OGR/GeoPackage sublayer name used to construct
  the QGIS URI.
- `id` carries the individual Rana child identifier.
- The parent request continues to carry the file-level `descriptor_id` through
  the file item.

`descriptor_id` is not reused as the child ID: it identifies the file
descriptor and is shared by all children. Layer IDs come from
`meta["layers"][].id`; table IDs come from the table record's `table_id`.

### Reuse existing persistent reference storage

No new persistent `table_id` field is planned. Opened tables reuse the
existing `RanaLayerRef.layer_id` field for their individual child identifier.
The child type remains available at request/opening time through
`VectorLayerRef` versus `VectorTableRef`.

The distinction is:

```text
VectorLayerRef / VectorTableRef
    request-time selection and dispatch information

RanaLayerRef
    persistent metadata attached to the opened QgsMapLayer
```

### Descriptor-driven Browser discovery

Browser expansion will use Rana descriptor metadata, not a download and local
file inspection. Spatial layers continue to use the existing layer metadata;
tables will be created from `meta["tables"]` once the table-name mapping is
confirmed.

This preserves the current lazy descriptor-fetch behavior and avoids making
simple Browser expansion download a complete file.

### Hybrid open-all verification

Opening a complete vector file will use both sources of information:

1. Descriptor metadata defines which layers and tables are supported and
   should be opened.
2. `QgsProviderRegistry.instance().querySublayers(local_file_path)` verifies
   the sublayers actually present in the downloaded file.
3. Spatial layers are opened from the descriptor layer entries.
4. Geometryless local sublayers are opened only when they match a
   descriptor-listed table.
5. Unlisted/internal geometryless sublayers are ignored.
6. A descriptor-listed table missing locally produces a warning, while other
   valid layers and tables continue opening.

This is deliberately safer than loading every `QgsWkbTypes.NoGeometry`
 sublayer reported by the provider, while retaining the legacy implementation's
 local-provider verification approach.

## Components

### Browser data items

- `data_items/file_item.py`: fetch descriptor metadata and create both layer
  and table children.
- `data_items/layer_item.py`: create `VectorLayerRef` when opening a layer.
- `data_items/table_item.py`: new leaf item creating `VectorTableRef` when
  opening a table.
- `utils/generic.py`: extend the existing icon map for table items.

### Request and loader flow

- `utils/data_models.py`: add `VectorLayerRef`, `VectorTableRef`, and
  `OpenVectorChildrenRequest`.
- `data_items/gui_provider.py`: aggregate mixed vector children by parent file.
- `loader.py`: download each parent file once and dispatch each child based on
  its concrete reference type; preserve file-level request deduplication.

### Layer management

- Add selected-table opening using a geometryless OGR `QgsVectorLayer`.
- Extend complete vector-file opening with provider sublayer inspection.
- Reuse the existing group hierarchy, Rana reference storage, error reporting,
  and layer-unlocking behavior.

## Data Model

The intended request model is:

```python
@dataclass(frozen=True)
class OpenVectorChildrenRequest:
    project: dict
    file_item: dict
    children: tuple[VectorLayerRef | VectorTableRef, ...]
```

The exact table construction is pending confirmation of the API's
`meta["tables"]` map-key semantics. Candidate mapping:

```python
VectorTableRef(
    name=table_map_key,              # pending confirmation
    id=table_metadata["table_id"],
)
```

No table-level display label or type is assumed because it is not present in
the researched API schema.

## Error Handling

- Descriptor fetch errors retain the existing Browser error-item behavior.
- A selected table that cannot be opened reports an item-specific error and
  does not add an invalid QGIS layer.
- A missing table during open-all warns and does not abort the complete file
  open.
- The existing communication/message-bar mechanism is reused.

## Testing Strategy

Tests should cover real behavior with a GeoPackage fixture containing spatial
layers and geometryless tables where QGIS/OGR is available.

Planned coverage:

- Browser expansion creates both layer and table children.
- Table item uses the existing theme icon path.
- Layer-only behavior remains unchanged.
- Single table opening.
- Mixed layer/table selection with one download per file.
- File-level open subsumes child requests without duplication.
- Open-all loads descriptor-listed layers and tables.
- Unlisted geometryless sublayers are ignored.
- Missing descriptor-listed tables warn and do not abort other opens.
- Opened tables receive the same Rana reference/group behavior as layers.

E2E tests are not included in this design without explicit approval. Manual
testing will be required for Browser expansion, single table opening, mixed
selection, file-level opening, and folder opening of vector files.

## Open Questions

1. What is the exact source of the canonical local table name? Is the outer
   key of `descriptor["meta"]["tables"]` guaranteed to be the GeoPackage
   table name?
2. Is the descriptor-level `layers` field equivalent to
   `descriptor["meta"]["layers"]`, and which one is authoritative for each
   current code path?
3. How should a table be associated with the descriptor's layer metadata when
   `meta["tables"][key]["layer_id"]` refers to a parent layer?
4. Is `table_id` stable and suitable for persistent `RanaLayerRef.layer_id`?
5. Which QGIS 4.x theme key is the correct native table icon for
   `get_file_icon_name()`?
6. Does the descriptor include views or other geometryless sublayers that
   should be treated differently from ordinary tables?

## Scope Boundaries

Included:

- Browser table children for vector files.
- Opening individual tables.
- Mixed layer/table opening.
- Opening all descriptor-listed layers and tables.
- Native QGIS icon reuse.
- Unit/integration coverage for the above.

Not included:

- Changes to the Rana API or descriptor schema.
- A new top-level file type for tables.
- Per-column Browser items or column editing UI.
- Automatic synchronization behavior specific to tables.
- E2E test additions without explicit approval.
