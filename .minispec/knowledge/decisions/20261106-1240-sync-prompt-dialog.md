---
type: decision
id: 20261106-1240-sync-prompt-dialog
date: 2026-11-06
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_prompt_dialog.py
  - rana_qgis_plugin/layer_management/close_sync_prompt.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
  - rana_qgis_plugin/layer_management/sync_summary.py
tags: [sync, messaging, ui]
participants: [engineer, build agent]
---

# One Collapsible Dialog For Close Prompt And On-Demand Sync

## Context
Users should see what a sync moves, on both routes: the on-demand sync from the layer panel
menu (informative, must not block) and the close and project-close prompt (a blocking
question). Listing every file in a message box gets long with many files or layers. The
details should be hidden by default, under a "More details" title, with a scrollable area
that appears only when needed. Each on-demand action syncs one kind (data or style); the
close prompt can have both.

## Options Considered
- **`QMessageBox.setDetailedText()`:** built into Qt, closed by default, scrolls when
  needed. Rejected. The toggle label is fixed to "Show Details...", and the text is plain
  only, so section headings cannot be bold.
- **Two separate dialogs:** rejected. Wording and layout would drift apart.
- **One dialog class, text built by callers:** rejected. Each caller would assemble the
  summary and details itself.
- **Base class plus two subclasses, base builds the details:** chosen.
- **Collection inside the dialog:** rejected. It needs QGIS layers and tree groups, which
  would make every dialog test depend on them.

## Decision
- `SyncPromptDialog` is the base. It shows a summary line, a "More details" box (collapsed
  by default on both routes) with a scrollable list, and a button row. It builds the
  details from a `SyncChanges`.
- `CloseSyncDialog` is modal, with "Sync now" and "Continue without syncing".
- `OnDemandSyncDialog` is non-blocking, with an OK button. It stays open until the user
  dismisses it, and several can be open at once. Its summary names the kind and the file
  count; the files and layers are under "More details".
- The details list changed layers per file under "Data changes" and "Style changes"
  headings. A file can appear in both. Empty sections are omitted. A single changed layer
  reads `file: layer`, several are a nested list.
- The close summary counts files per kind, for example
  `3 files have unsynced changes (data: 2, style: 2).`

## Consequences
- The close and project-close prompts and the on-demand notice do not use `QMessageBox` or
  `communication.custom_ask`. Tests that answer them target the dialog classes.
- Capture must record every dirty layer per file, not one name per file item; see
  `20261109-1100-sync-changes-model`.
- Formatting stays free of QGIS imports and is tested without widgets.
