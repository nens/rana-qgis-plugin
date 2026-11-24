---
type: decision
id: 20261124-1000-revision-upload-pre-dialog-bars
date: 2026-11-24
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
tags: [upload, save-revision, message-bar, progress]
participants: [margriet, agent]
---

# Revision upload: pre-dialog busy bars are sequential and self-cleaning

## Context

Creating a new revision (layer panel or Browser item) pushes many message-bar
items. The flow has three phases: pre-dialog (layer save, API fetch),
in-dialog (`UploadWizard`) and post-dialog (`SchematisationUploadTask`).
Only pre- and post-dialog message-bar items are in scope; the wizard's
own messages are not.

Pre-dialog today: `save_revision` pushes a "preparing for save revision" busy
bar that does not paint (the fetch is synchronous) and is only removed when the
wizard is cancelled. `commit_opened_revision` pushes one "Save changed layers"
bar per edited layer and then calls `clear_message_bar()`, which also removes
unrelated items.

## Options Considered

### Option A: Two sequential bars, each owned by the method that creates it

- ✅ `save_revision` signature unchanged
- ✅ Each method removes exactly what it created
- ❌ Two short-lived busy bars in a row when the layer path saves edits

### Option B: One pending bar created at the entry point, passed to `save_revision`

- ✅ Strictly one pre-dialog bar
- ❌ Changes `save_revision` signature
- ❌ In the Browser path it would sit behind the confirmation dialog

## Decision

**Option A.**

- `commit_opened_revision` shows one "Saving layer changes" busy bar (not one
  per layer) and removes exactly that item when saving ends, on success or
  failure.
- `save_revision` shows one "Preparing revision upload" busy bar, processes
  events once so it paints, and removes exactly that item before
  `UploadWizard.exec()` and on every early return.
- This flow no longer calls `clear_message_bar()`.

## Consequences

- The pending bar is visible until the dialog appears and never outlives it.
- Unrelated message-bar items survive a revision upload.
