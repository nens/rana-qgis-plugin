# Decision: Pre-check conflicts on the main thread

**Date:** 2026-08-12
**Status:** Accepted

## Decision

Use the ported `FileUploadWorker` logic to process new-file conflicts and
upload initiation sequentially before launching the task. Use the ported
`ExistingFileUploadWorker` logic for future re-upload callers.

For new files, exact matches fail unless the user chooses overwrite; a
case-insensitive match at initiation uses the same dialog. Both dialogs offer:
Overwrite this file, Overwrite all conflicts, Skip this file, and Abort.

Shapefile conversion offers: Convert this file only, Convert all shapefiles,
Skip this file, and Abort.

Skip continues with later files. Abort stops the complete batch before the
background task starts. Apply-to-all choices suppress later matching dialogs.

## Reasoning

The main thread is the only place where dialogs are safe. Sequential
prechecking gives predictable bulk-upload behaviour and ensures the task can
run without waiting for user input.
