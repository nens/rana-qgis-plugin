---
feature: feat_485_open_vector_tables
status: planned
created: 2026-09-29
decisions: []
---

# Open Vector Tables Design

## Overview

Extend the Rana QGIS Browser and vector-file opening flow to support
geometryless tables in addition to spatial vector layers.

The feature has four goals:

1. Show tables when a Rana vector file is expanded in the Browser.
2. Allow an individual table to be opened, including selections containing a
   mixture of layers and tables.
3. Keep whole-file opening GeoPackage-authoritative for now: open the local
   sublayers discovered from the downloaded GeoPackage.
4. Align Browser layer discovery with the layer manager by reading layers
   from `descriptor["meta"]["layers"]` instead of the root-level
   `descriptor["layers"]` field.

The design extends the existing vector-file flow. Tables are not introduced
as a new top-level Rana file type.

## Current API/schema observation

The vector descriptor's `meta` field is confirmed to be structured as
follows:

- `meta["layers"]` (required): array of layer entries, each with `id`,
  `name`, and `type`.
- `meta["tables"]` (optional): dict keyed by table ID, each value containing
  `layer_id`, `table_id` (matching the dict key), and `columns`.

For this feature, only `table_id` is needed: it matches the corresponding
table name in the GeoPackage. `layer_id` and `columns` are intentionally not
used, and tables are not linked to layers in the Browser.

```python
descriptor["meta"]["layers"] = [
    {
        "id": "layer-child-id",
        "name": "roads",
        "type": "Polygon",
    },
]

descriptor["meta"]["tables"] = {
    "<table-id>": {
        "layer_id": "base-table-name-of-related-layer",
        "table_id": "table-id",
        "columns": {...},
    },
}
```

### Backend source: Rana ADR 046 (Tabular Data in Vector Files)

[ADR 046](https://github.com/nens/rana/blob/main/design/046_vector_table_data.md)
describes the backend's source of `meta["tables"]` and confirms/refines parts
of the schema above:

- Tables originate from the GeoPackage **Related Tables Extension (RTE)**: a
  process emits a GeoPackage with a geometry layer, a related non-spatial
  table, and an entry in `gpkgext_relations` linking them via a
  `relation_name` (currently only `simple_attributes` exists; the ADR
  reserves the field for future relation types).
- The backend scans `gpkgext_relations` and adds one entry to
  `meta["tables"]` per relation, keyed by `table_id`. Related tables are
  excluded from `meta["layers"]`.
- The ADR's backend model:
  ```python
  class Table:
      table_id: str  # related_table_name in gpkgext_relations
      layer_id: str  # base_table_name in gpkgext_relations
      columns: dict[str, TableColumn]  # keyed by column name

  class TableColumn:
      column_id: str
      label: str | None
      unit: UnitOfMeasure | None
  ```
- The full related table still physically exists in the downloaded
  GeoPackage (the S3/JSON extraction is only for a separate backend
  `gpkg-table` chart view used by the web frontend). This confirms the
  plugin's local-file, OGR-based opening approach does not need to call any
  new API.

**What this resolves:** the `meta["tables"]` dict key is confirmed to be
`table_id`, and `table_id` is the literal GeoPackage related-table name used
to open the table from the local GeoPackage.

The table-to-layer association described by `layer_id` is intentionally out
of scope. The feature will not inspect or use `layer_id` to associate tables
with layers.

The ADR's `Table`/`TableColumn` model also has no `relation_name` field, so
the file descriptor does not expose which relation type a table came from.
Today that's immaterial (only `simple_attributes` exists), but it is a
forward-compatibility gap if the backend introduces other relation types
later. See Open Questions.

### Root vs. meta layers discrepancy (to be fixed by this feature)

`data_items/file_item.py` currently expands vector file Browser children
from the descriptor-level `layers` field (`descriptor.get("layers", [])`),
while `layer_management/layer_manager.py` opens layers from
`descriptor["meta"]["layers"]`. These are confirmed to be two different
locations in the descriptor, and `meta["layers"]` is authoritative.

As part of this feature, `file_item.py` will be updated to read from
`descriptor["meta"]["layers"]` instead of the root-level field, so Browser
expansion and layer opening use the same source. This resolves the
discrepancy previously recorded as an open question.

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
4. **Given** a descriptor where the root-level `layers` field and
   `meta["layers"]` differ, **when** the file is expanded, **then** Browser
   children are built from `meta["layers"]`.

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

### User Story 3 - Open a complete vector file (Priority: P1; authority pending)

As a user, I want opening a vector file to include its spatial layers and
geometryless tables. Whether descriptor metadata filters which local
sublayers are included is pending PM/designer input; for now the GeoPackage is
authoritative.

**Independent Test**: Open a downloaded GeoPackage containing spatial layers
and geometryless tables and verify that its local sublayers are present in the
QGIS layer tree.

**Acceptance Scenarios**:

1. **Given** a vector GeoPackage with spatial and geometryless sublayers,
   **when** the file is opened, **then** the existing OGR-based path attempts
   to open all local sublayers.
2. The descriptor-vs-GeoPackage filtering behavior remains undecided and is
   deferred as described in Whole-file opening policy (temporary).

## Design Decisions So Far

### Dedicated Browser item for tables

Tables will be represented by a new `RanaTableDataItem`, separate from
`RanaLayerDataItem`.

This keeps geometry-bearing layers and geometryless tables explicit in the
Browser model and allows their opening behavior to be selected by type.

Table items are flat siblings of layer items directly under the vector file
item. They are not nested under or otherwise linked to layer items.

### Reuse the existing icon mechanism

Table items will use the same path as spatial layer items, using the native
QGIS `mIconTableLayer.svg` theme icon:

```text
table metadata/type
    -> get_file_icon_name(...)
    -> get_icon_from_theme(...)
```

The implementation should add the table mapping to the existing generic icon
map. No separate icon helper or bundled plugin asset is needed.

### Unified selected-child request

Selected layers and tables will use one request type named
`OpenVectorFileRequest`, rather than separate layer and table request
pipelines. Each request is for one parent vector file and its selected
children; the loader downloads the file once and dispatches each child by its
reference type. `OpenFileRequest` remains the request for opening every
supported content in a file.

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
For this feature, `table_id` is assumed to remain stable across reprocessing.
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
tables will be created from `meta["tables"]`, using `table_id` as the local
GeoPackage table name. `layer_id` and `columns` are ignored.

This preserves the current lazy descriptor-fetch behavior and avoids making
simple Browser expansion download a complete file.

### Whole-file opening policy (temporary)

For now, the downloaded GeoPackage is authoritative when opening a complete
vector file. The existing whole-file flow discovers and opens its local
sublayers through OGR, including geometryless tables. It does not filter those
sublayers against the Rana descriptor, so a local sublayer absent from
`meta["layers"]` or `meta["tables"]` may also be opened.

This is a temporary scope decision while product/design input is pending. The
alternative is to make the Rana descriptor authoritative and open only its
listed layers and tables. Revisit the policy after the PM and designer decide.

## Components

### Browser data items

- `data_items/file_item.py`: fetch descriptor metadata and create both layer
  and table children, reading layers from `descriptor["meta"]["layers"]`
  (replacing the previous root-level `descriptor["layers"]` lookup) and
  tables from `descriptor["meta"]["tables"]`.
- `data_items/layer_item.py`: create `VectorLayerRef` when opening a layer.
- `data_items/table_item.py`: new leaf item creating `VectorTableRef` when
  opening a table.
- `utils/generic.py`: extend the existing icon map for table items.

### Request and loader flow

- `utils/data_models.py`: add `VectorLayerRef`, `VectorTableRef`, and
  `OpenVectorFileRequest`.
- `data_items/gui_provider.py`: aggregate every selected vector child
  (layer-only, table-only, or mixed) into exactly one `OpenVectorFileRequest`
  per parent file.
- `data_items/layer_item.py` and `data_items/table_item.py`: submit a one-child
  `OpenVectorFileRequest` for their selected child.
- `loader.py`: download each parent file once, merge child refs when duplicate
  requests target the same file, and dispatch each child by its concrete ref
  type; a whole-file `OpenFileRequest` subsumes the selected-vector request.

### Layer management

- Add selected-table opening using a geometryless OGR `QgsVectorLayer`.
- Whole-file opening currently treats the GeoPackage as authoritative; the
  descriptor-vs-GeoPackage policy remains pending product/design confirmation.
- Reuse the existing group hierarchy, Rana reference storage, error reporting,
  and layer-unlocking behavior.

## Data Model

The intended request model is:

```python
@dataclass(frozen=True)
class OpenVectorFileRequest:
    project: dict
    file_item: dict
    children: tuple[VectorLayerRef | VectorTableRef, ...]
```

The table construction, per ADR 046 (see Current API/schema observation), is:

```python
VectorTableRef(
    name=table_metadata["table_id"],  # local GeoPackage table name
    id=table_metadata["table_id"],
)
```

No table-level display label or type is assumed because it is not present in
the researched API schema.

## Error Handling

- Descriptor fetch errors retain the existing Browser error-item behavior.
- A selected table that cannot be opened reports an item-specific error and
  does not add an invalid QGIS layer.
- Whole-file opening follows the current GeoPackage-authoritative behavior;
  opening only descriptor-listed tables is deferred pending product/design
  confirmation.
- The existing communication/message-bar mechanism is reused.

## Testing Strategy

Tests should cover real behavior with a GeoPackage fixture containing spatial
layers and geometryless tables where QGIS/OGR is available.

Planned coverage:

- Browser expansion creates both layer and table children.
- Browser expansion sources layers from `meta["layers"]`, not the root-level
  `layers` field.
- Table item uses the existing theme icon path.
- Layer-only behavior remains unchanged.
- Single table opening.
- Mixed layer/table selection with one download per file.
- File-level open subsumes child requests without duplication.
- Whole-file opening behavior follows the GeoPackage-authoritative policy for
  now; descriptor filtering is deferred pending product/design confirmation.
- Opened tables receive the same Rana reference/group behavior as layers.

E2E tests are not included in this design without explicit approval. Manual
testing will be required for Browser expansion, single table opening, mixed
selection, file-level opening, and folder opening of vector files.

## Open Questions

1. **Whole-file authority (pending PM/designer decision).** Should opening a
   complete vector file use every sublayer in the downloaded GeoPackage, as it
   currently does, or only layers/tables listed in the Rana descriptor? For
   now, the GeoPackage is authoritative so implementation can proceed.
2. **Forward-compatibility gap.** ADR 046 reserves `relation_name` for future
   relation types beyond `simple_attributes`, but the file descriptor's
   `Table` model does not expose `relation_name`. The plugin currently cannot
   distinguish table "kinds" from the descriptor alone. Not a blocker today
   (only one relation type exists), but a design should be revisited if the
   backend introduces semantically different tabular relations.

### Resolved since initial draft

- Whether the descriptor-level `layers` field is equivalent to
  `descriptor["meta"]["layers"]`, and which is authoritative: `meta["layers"]`
  is authoritative. `file_item.py` will be updated to read from it, removing
  the root-level `layers` lookup (see goal 4 and Components).
- Whether the `meta["tables"]` dict key is guaranteed to equal the canonical
  local GeoPackage table name: confirmed by ADR 046. The key is `table_id`,
  which is the literal `related_table_name` from `gpkgext_relations`.
- Whether tables should be associated/nested under layers: not for this
  feature. Table items are flat siblings, and `layer_id` is ignored.
- Whether `table_id` is stable across reprocessing: assumed stable for this
  feature and reused as the persistent `RanaLayerRef.layer_id`.
- Which native QGIS theme icon to use for table items: use
  `mIconTableLayer.svg`, QGIS's icon for non-spatial table layers.

## Scope Boundaries

Included:

- Browser table children for vector files.
- Opening individual tables.
- Mixed layer/table opening.
- Opening all descriptor-listed layers and tables.
- Native QGIS icon reuse.
- Switching `file_item.py` Browser layer discovery to `meta["layers"]`.
- Unit/integration coverage for the above.

Not included:

- Changes to the Rana API or descriptor schema.
- A new top-level file type for tables.
- Per-column Browser items or column editing UI.
- Automatic synchronization behavior specific to tables.
- E2E test additions without explicit approval.
