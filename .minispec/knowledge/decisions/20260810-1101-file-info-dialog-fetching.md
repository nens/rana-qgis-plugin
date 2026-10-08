# File info uses a synchronous refreshable dialog

**Status:** Accepted  
**Date:** 2026-08-10

## Context

Opening or refreshing file information requires a network request to the file-descriptor endpoint. This is a single, small request in a modal information dialog.

## Decision

Open a modal `QDialog` for one file and fetch its descriptor synchronously on open and on demand when Refresh is pressed. Use the existing avatar worker/cache for author avatars.

## Rationale

A dialog has a simple lifecycle and matches the context-menu interaction. Synchronous fetching keeps this small feature aligned with the existing dialog pattern and avoids adding worker lifecycle complexity for one request. One fetch path serves both initial load and refresh.

## Consequences

- The dialog needs loading, failure, and refresh-state handling. The Refresh control should visibly indicate that the dialog is temporarily busy.
- If real-world latency shows that the request is too slow, asynchronous fetching can be introduced later without changing the model/view boundary.
- The action is read-only: action buttons and rename remain out of scope.
