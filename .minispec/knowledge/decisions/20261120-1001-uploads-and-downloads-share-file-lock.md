---
id: 20261120-1001-uploads-and-downloads-share-file-lock
date: 2026-11-20
status: accepted
---

# Uploads and downloads share one per-file lock

## Decision

Downloads take the same `LayerLockRegistry` key as uploads. The key is
`(project_id, file_id)`, built by one shared `sync_key` function used by data
uploads, style uploads, `layers_for_keys` and downloads. `descriptor_id` is not
part of the key: the server assigns a new one on every upload, so a layer ref
and a folder listing can disagree about it for the same file. A download of a
file that is being uploaded is refused with a message (skipped, with a count,
when part of a folder open). An upload of a file being downloaded is refused by
the existing "sync already in progress" message.

## Rationale

`download_url` opens the local file with `"wb"` and rewrites it in place. A
reopen during an upload corrupts the upload and may discard the local edits
being uploaded. Once the upload finishes, local and server copies are equal, so
blocking (instead of queueing) the open loses nothing.
