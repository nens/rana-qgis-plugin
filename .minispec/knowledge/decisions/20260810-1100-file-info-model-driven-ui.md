# File info uses stable model-driven UI

**Status:** Accepted  
**Date:** 2026-08-10

## Context

The legacy file information widget recreates `QgsCollapsibleGroupBox` contents during refresh and contains many data-type conditionals. Users report problems with the group boxes. The replacement must preserve the full information view while remaining easy to migrate to tabs or a scrollable form if needed.

## Decision

Use a base `FileInfoModel` with specialized `ScenarioInfoModel` and `SchematisationInfoModel` subclasses. The dialog creates stable group boxes and child views once, then updates their contents from the model. The initial layout remains the group-box layout, including the related-files table.

## Rationale

Separating descriptor transformation from rendering prevents refresh from destroying and recreating containers. Specialized models keep type-specific behavior out of the view. Keeping the renderer behind the model boundary makes a later tabs or scroll migration local to the dialog.

## Consequences

- Additional model and table-model code is required.
- Models must normalize missing descriptor fields and represent loading/error states.
- Group-box behavior can be replaced later without changing fetching or descriptor transformation.
