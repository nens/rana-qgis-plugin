# Decision: Add Retry Logic for Schematisation Style Upload

**Date:** 2026-04-15 11:15  
**Status:** Accepted

## Decision

Add optional retry logic to `FileDescriptorStyleUploadWorker` to handle cases where the style upload endpoint is not yet ready (returns 404).

## Problem

The schematisation style upload endpoint may not be ready immediately after export, causing uploads to fail. We need a way to retry with user feedback.

## Solution

1. **Create `RanaEndPointNotFoundError`** exception for 404 responses
2. **Extend `upload_file_styling()`** to raise `RanaEndPointNotFoundError` on 404
3. **Add `retry_timeout_seconds` parameter** to `FileDescriptorStyleUploadWorker`
   - `0` = no retry (default for backward compatibility)
   - `> 0` = retry for that many seconds
4. **Implement `_upload_with_retry()` method** in worker:
   - Shows "Waiting for style upload..." message
   - Sets progress bar to busy mode (min=max=0)
   - Retries with 2-second delays
   - Stops on success or timeout
   - Restores previous UI state on completion

## Implementation Details

- Retry only on `RanaEndPointNotFoundError` (404 status)
- Other `FetchError` exceptions fail immediately
- Caller controls retry behavior via constructor parameter
- Only schematisation uploads will use retry (passed from loader.py)

## Files to Modify

1. `rana_qgis_plugin/utlis/api.py` - Add exception, modify `upload_file_styling()`
2. `rana_qgis_plugin/workers/styling.py` - Add retry parameter and method to worker
3. `rana_qgis_plugin/loader.py` - Pass `retry_timeout_seconds=60` for schematisation uploads
