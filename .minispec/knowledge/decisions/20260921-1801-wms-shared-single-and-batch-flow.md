---
id: 20260921-1801-wms-shared-single-and-batch-flow
status: accepted
date: 2026-09-21
---

# Share per-scenario WMS processing

## Context

Open WMS must work for a single scenario and for multiple scenarios. Both
flows need the same descriptor fetch, WMS-link validation, layer extraction,
and layer creation. Unlike result opening, WMS opening does not download files
or resolve 3Di metadata.

## Decision

Introduce `OpenScenarioWmsRequest` as a request type separate from
`OpenScenarioRequest`. Implement one per-scenario loader helper and have both
the single-item entry point and the batch entry point delegate to it. Process
requests synchronously; do not introduce a `QgsTask` for this metadata-only
operation.

## Rationale

The separate request type keeps result downloading and WMS opening explicit in
loader dispatch. Sharing the per-scenario helper prevents behavior drift and
duplicate error handling. Synchronous execution matches existing descriptor
fetching and avoids task lifecycle complexity for a short operation.
