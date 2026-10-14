# Track raster data changes with a layer-scoped file fingerprint

**Date:** 2026-10-21
**Status:** Accepted
**Feature:** feat_470_file_sync

## Context

QGIS raster layers do not expose an edit buffer or a data-modified signal.
Changes made through QGIS tools are written to the data source on disk, so
signal-based tracking cannot reliably identify unsynced raster edits. Rana
uploads send the main raster source file; sidecars are not included in the
data upload.

The plugin already stores Rana identity and dirty state as layer custom
properties. Keeping a raster baseline there is consistent with that model;
there is no need for a separate project- or global-scoped metadata store.

## Decision

For Rana-linked, GDAL-backed raster layers whose source resides under
`rana_cache_dir()`, compare a stat-based fingerprint of the main source file
against a baseline captured after successful download or data upload.

The fingerprint is a truncated `sha256` digest of the source file name, size,
and nanosecond mtime. It does not read file contents, so calculation cost is
independent of raster byte size. Sidecars—including style `.qml` and auxiliary
metadata—are not uploaded with the raster and do not contribute to its dirty
state. A byte-identical rewrite of the main file may conservatively report
dirty; content hashing is deferred unless this creates practical noise.

Store the baseline as the layer custom property `rana/data_fingerprint`, not
in QSettings or another global/project-independent store. Missing baseline or
an ineligible source means `UNKNOWN`; opening a pre-existing file must not
implicitly bless it as clean. A successful re-download is a known-in-sync
event and replaces the baseline after the downloaded file is complete, so the
new local copy is clean unless changed again.

Use filesystem notifications with debouncing to refresh state during a QGIS
session. Revalidate at project/layer startup and before close/removal prompt
collection; context-menu and badge refresh read cached dirty properties and
must not scan directories. Vectors remain on `afterCommitChanges` and are not
included in filesystem tracking.

## Consequences

- Raster dirty state persists with the layer/project and shares the lifecycle
  of existing Rana custom properties; unlinking removes the baseline.
- `rana/data_dirty` remains the consumer-facing state, so existing badge,
  menu, and prompt paths can use their shared dirty-state predicates.
- A project without a saved baseline may report `UNKNOWN`, which is safer than
  asserting that an existing local file is clean.
- Watch only the main source file that is uploaded to Rana. Refresh its watch
  after a change at the same path to handle atomic replacement; stop tracking
  if the source is removed or renamed. Remove watches when layers are removed
  or the plugin disconnects.
- Filesystem tracking does not detect a change that happens and is reverted
  to the exact same size and nanosecond mtime between evaluations. This narrow
  limitation is accepted for the stat-only approach.
