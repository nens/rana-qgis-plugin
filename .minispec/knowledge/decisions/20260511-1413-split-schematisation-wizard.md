# Decision: Split schematisation wizard into two independent classes

**Date**: 2026-05-11  
**Status**: Superseded by `20261009-1200-unify-schematisation-wizard-base-and-flow`
**Feature**: Split schematisation creation (feat_4224_upload_existing_)

---

## Context

The existing `NewSchematisationWizard` combined two distinct user flows in one class:
1. Create a new schematisation with a fresh empty GeoPackage
2. Create a schematisation from an existing GeoPackage file

The radio button UI in `SchematisationNamePage` controlled which branch was taken, and the wizard conditionally showed or skipped additional pages (Explain, Settings) depending on the selection.

The request was to split these into two separate entry points, with the file picker for the "upload existing" flow appearing *before* the wizard opens.

---

## Decision

Use **two independent wizard classes** (`NewSchematisationWizard` and `UploadExistingSchematisationWizard`) sharing a **module-level helper function** (`_create_schematisation_base`) rather than a base class / subclass hierarchy.

`get_paths_from_geopackage` is promoted from a `@staticmethod` to a module-level function.

`SchematisationNamePage` gains a `show_gpkg_selector` flag (default `False`) to conditionally render the GeoPackage file selection UI, but this is only used for backward compatibility — both new wizard classes pass `False`.

---

## Alternatives Considered

**Option A: Single wizard with `mode` parameter**  
Rejected — would add conditional logic throughout the existing class without improving clarity.

**Option B1: Subclass hierarchy**  
Considered — would share constructor boilerplate and `get_paths_from_geopackage` via inheritance. Rejected because the two page structures are different enough that the base class would need awkward abstract/overridable page setup, and the shared logic is better expressed as a plain function.

**Option B2: Two independent classes + shared helper** *(chosen)*  
Each class is simple and self-contained. Shared logic lives in a module-level function. No inheritance to reason about.

---

## Consequences

- `NewSchematisationWizard` class name is preserved; no change needed at its call site
- `loader.py` gets a new slot `upload_existing_schematisation_to_rana` mirroring the existing one
- File picker for "upload existing" flow is shown in `loader.py` before the wizard, not inside the wizard
- `SchematisationNamePage` gpkg UI can be fully removed in both wizards (neither needs it)
