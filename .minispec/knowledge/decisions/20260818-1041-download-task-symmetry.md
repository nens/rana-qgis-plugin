# Download: Reuse Legacy Downloader/Context Split, Port Worker to QgsTask

**Date:** 2026-08-18
**Status:** Accepted

## Context

Opening a Rana file into QGIS requires downloading it first. No download
mechanism exists yet in the new (`QgsDataItemProvider`) architecture —
only `UploadTask(QgsTask)` exists today (`utils/upload.py`), used for
uploading new files.

Legacy (`legacy/workers/download.py`) already solved this with a
three-part structure:

- **Downloader** (`BaseDownloader` / `RanaDownloader` / `RanaFileDownloader`)
  — knows *what* to download and how to post-process it (style zip
  extraction, raster QML rescaling)
- **Download context** (`AbstractDownloadContext` / `FileDownloadContext` /
  `TempDownloadContext`) — knows *where* to download to
- **Download worker** (`SingleFileDownloadWorker` / `BatchFileDownloadWorker`)
  — drives one or more downloaders, built on `QThread`

The legacy worker layer has the known QThread lifecycle issues called out
elsewhere in this codebase (tangled signal chains, cleanup-on-reload
crashes) — but the downloader/context split above it is sound and doesn't
need to be redesigned.

## Decision

Reuse the `Downloader`/`DownloadContext` split as-is (or lightly adapted),
and replace only the worker layer with a new `DownloadTask(QgsTask)`,
mirroring the existing `UploadTask`.

New `OpenFileDownloadContext(AbstractDownloadContext)` resolves paths under
a new **open cache directory** setting (`rana_open_cache_dir()`), separate
from the existing `rana_cache_dir()`.

## Reasoning

- Same rationale as the existing upload-threading decision
  (`.minispec/knowledge/decisions/20260812-1529-upload-threading-model.md`):
  file transfer can take from sub-second to minutes depending on size, so
  it must not block the UI thread
- Unlike rename/delete/create-folder (deliberately synchronous per
  `.minispec/knowledge/decisions/20260817-1400-sync-context-menu-operations.md`),
  download involves an actual file transfer, not a fast POST — the same
  reasoning that keeps upload async applies here
- Mirroring `UploadTask`'s structure keeps the codebase consistent — one
  established pattern for background file transfer, not two
- Reusing the downloader/context classes avoids re-solving already-proven
  problems (style zip extraction, raster QML rescaling) and keeps the
  "known issues are in the worker/threading layer, not the
  downloader/context layer" distinction from `AGENTS.md`'s legacy-code
  guidance intact
- A separate `rana_open_cache_dir()` (defaulting to the OS temp dir, e.g.
  `/tmp` on Linux) is used instead of reusing `rana_cache_dir()` (defaults
  to `~/Rana`) because files opened via "Open in QGIS" are disposable
  working copies backing a layer-panel item, not files the user
  deliberately downloaded/cached — they shouldn't clutter or share
  retention/cleanup policy with the user-facing cache folder

## Consequences

- While a file's own download is in flight, re-triggering "open" for the
  same file is a no-op (or shows "already opening") rather than starting a
  second concurrent download
- Batch/folder-open de-duplication (a file already downloaded once,
  shared across multiple opened layers) can reuse the pattern from
  `BatchFileDownloadWorker.handle_existing()`, adapted to `QgsTask`
- A new `QgsSettings` entry (`open_cache_dir`) is introduced, following
  the same get/set pattern as `rana_cache_dir()`/`set_rana_cache_dir()`
- Moving `legacy/workers/download.py` (and `layer_manager.py`,
  `legacy/workers/styling.py`) out of `legacy/` removes them from mypy's
  blanket `legacy.*` exemption, surfacing ~50 pre-existing latent type
  errors. `mypy.ini` now carries temporary per-module `ignore_errors = True`
  entries for these three files specifically, to be removed once each is
  actually adapted to the new architecture (tracked as a definition-of-done
  item per phase in `design.md`) — not a permanent carve-out

## Related Decisions

- `.minispec/knowledge/decisions/20260812-1529-upload-threading-model.md`
- `.minispec/specs/feat_454_open_generic_files/design.md` (Phase 1)

## Code References

- Reused structure: `rana_qgis_plugin/legacy/workers/download.py` (`BaseDownloader`, `RanaDownloader`, `RanaFileDownloader`, `AbstractDownloadContext`, `FileDownloadContext`, `TempDownloadContext`)
- Pattern to mirror: `rana_qgis_plugin/utils/upload.py` (`UploadTask`)
- Existing cache-dir setting to parallel: `rana_qgis_plugin/utils/settings.py` (`rana_cache_dir`, `set_rana_cache_dir`)
