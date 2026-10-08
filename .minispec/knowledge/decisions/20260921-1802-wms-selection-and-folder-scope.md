---
id: 20260921-1802-wms-selection-and-folder-scope
status: accepted
date: 2026-09-21
---

# Gate WMS by selection and process scenario files in folders

## Context

The file action already exposes Open WMS only for scenario files. The GUI
provider intersects actions across a multi-selection. Folders are resolved
lazily and may contain mixed file types.

## Decision

Add `FileAction.OPEN_WMS` to the existing multi-select whitelist. Rely on the
existing intersection behavior to expose it only when every selected file is a
scenario. Keep Open WMS as a context-menu action; double-click continues to
open scenario results.

Folders expose the action through their existing folder-action path. At
execution time, resolve the folder and create WMS requests only for entries
with `data_type == "scenario"`. Mixed folders are allowed: non-scenario files
are skipped and a summary is shown. Folder processing is not performed during
context-menu construction, so right-clicking does not trigger an eager network
fetch.

## Rationale

The existing action intersection gives the required all-scenarios restriction
for direct multi-selection without new classification logic. Lazy folder
resolution avoids network work merely to construct a menu, while still
supporting the requested folder workflow. Skipping unrelated files keeps the
folder action useful for normal mixed-content folders.
