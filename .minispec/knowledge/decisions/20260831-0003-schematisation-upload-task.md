# Decision: Use a QgsTask for revision uploads

- **Date:** 2026-08-31
- **Status:** accepted

## Context

`legacy/loader.py::Loader.save_revision` uses legacy thread-pool and manual
thread lifecycle patterns. The modern open/download flow already uses QGIS
tasks, and uploads can be long-running network operations.

## Decision

Implement the save-revision upload worker as a `QgsTask`. Keep dialogs and QGIS
layer-tree changes on the main thread, and perform network/file processing in
the task.

## Rationale

This keeps QGIS responsive and follows the modern task lifecycle without
copying known legacy threading problems.

## Consequences

The port must translate legacy progress, cancellation, success, and failure
signals into the `QgsTask` lifecycle. UI callbacks must not mutate Qt objects
from the worker thread.
