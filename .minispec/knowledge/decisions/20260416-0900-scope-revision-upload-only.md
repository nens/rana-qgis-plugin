# Decision: Scope revision upload error feedback only

**ID:** 20260416-0900-scope-revision-upload-only
**Date:** 2026-04-16
**Status:** Accepted

## Context

The original plan covered three workflows: "Upload schematisation", "Start simulation",
and "New schematisation". Investigation showed that two of those already work correctly.

## Decision

Implement error feedback only for the schematisation revision upload workflow.

## Reasoning

- "Start simulation" (`SimulationRunner`) already catches `ApiException` with
  `extract_error_message` and the error reaches `bar_error` via `on_initializing_failed`.
- "New schematisation" (`NewSchematisationWizard`) already has per-call `except ApiException`
  blocks using `extract_error_message` and calls `bar_error` directly.
- `ApiErrorContext` helper class from the original plan is not needed — `extract_error_message`
  already exists and covers the API response parsing.

## Consequences

Smaller, lower-risk change. Two files modified instead of four.
