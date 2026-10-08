---
id: 20260429-1101-download-required-files-no-dialogs
date: 2026-04-29
status: accepted
---

# Remove dialogs from download_required_files

## Decision

`simulation/utils.download_required_files` is simplified to always use the WIP slot
and always replace existing local data, with no user-facing dialogs.

## Rationale

Dialogs inside a download function prevent it from being called in a batch context.
The simpler behaviour (always WIP, always replace) is the right default for both
single and batch downloads, removing unnecessary decision points for the user.
