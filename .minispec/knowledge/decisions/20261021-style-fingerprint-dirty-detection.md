# Detect style changes by fingerprint, not by signal

**Date:** 2026-10-21
**Status:** Rejected for now (deferred 2026-10-21)
**Feature:** feat_470_file_sync

> **Deferred.** This design is sound but is not being implemented. Manual
> testing reports dirty state tracking correctly in normal use, and the
> mechanism costs ~345 lines across three tasks while carrying the feature's
> highest implementation risk. The holes in the Context section are source
> readings, not observed failures.
>
> Revive this decision if **either** trigger fires:
>
> 1. A map-label edit through the Layer Styling dock leaves `rana/style_dirty`
>    unset (confirms the labeling hole is reachable in practice). Note the
>    labeling hole was inferred from `setLabeling()` alone; whether the real UI
>    paths call `emitStyleChanged()` anyway was never established.
> 2. ~~KI-004 is confirmed as a real false positive, since neither candidate
>    emitter changes serialised style content and this is the mechanism that
>    would make them harmless.~~ **Withdrawn 2026-10-21.** KI-004 was
>    confirmed, but its cause was unrelated to signals: Rana's custom
>    properties were round-tripping through the uploaded `.qml`, so
>    `loadNamedStyle` restored `rana/style_dirty` directly. A fingerprint
>    would not have prevented that. Fixed by stripping `rana/*` from QML on
>    both save and load; this trigger no longer applies.
>
> Until then `styleChanged` remains the detection mechanism.

## Context

`attach_dirty_tracking` sets `rana/style_dirty` from `QgsMapLayer.styleChanged`.
That signal is not emitted by QGIS automatically when a style changes — it is
emitted imperatively, by each editing widget calling `emitStyleChanged()`.
Coverage is therefore per-caller and incomplete.

Confirmed against QGIS 4.2.3 (`release-4_2` @ `2d2f433`):

- `QgsVectorLayer::setLabeling()` emits nothing, so labeling edits are never
  marked dirty — despite `qgsmaplayer.h:2096` explicitly promising the signal
  covers "label style changes".
- Vector-tile and annotation layers never emit it at all.
- Conversely, `QgsMapLayerStyleManager::setCurrentStyle()` and a Layer Styling
  dock `apply()` emit it without the user having edited anything.
- The layer-tree colour wheel emits once per mouse-move sample during a drag.

So the signal produces false negatives, false positives, and storms. Not a
single one of these is fixable by choosing a different signal:
`rendererChanged` is strictly narrower, and `repaintRequested` is far broader
(it also fires on data edits, selection changes and refresh timers).

## Decision

Detect style changes by comparing a **content fingerprint**, with the signal
demoted to a cheap hint about when to look.

1. Capture a baseline inside `attach_dirty_tracking`, after any sidecar
   `.qml` has been applied: serialise via `QgsMapLayer.writeStyle()` into a
   `QDomDocument`, then hash `doc.toString()`.
2. Connect `repaintRequested` to a per-layer single-shot `QTimer`, debounced
   at **100 ms** — the interval QGIS itself uses in
   `QgsLayerStylingWidget::autoApply()`.
3. On timer fire, recompute and compare. Set `rana/style_dirty` only when the
   fingerprint actually differs.
4. Keep `styleChanged` connected, routed through the same comparison, so it
   can no longer produce false positives.
5. On successful sync, `clear_dirty` must **re-baseline** the fingerprint, or
   the layer re-dirties on the next repaint.

Use `writeStyle()` rather than `saveNamedStyle()` (which touches disk) or
`styleURI()` (which returns a path and says nothing about in-memory state).

## Rationale

This is the approach QGIS core takes for the same problem, in two places:

- `QgsLayerStyleWatcher` (`src/3d/qgslayerstylewatcher.cpp`, new in 4.2)
  listens to `repaintRequested`, not `styleChanged`, with the in-tree comment
  *"its 2D style changed"*. It is `///@cond PRIVATE` / `SIP_NO_FILE`, so it
  is precedent only — not usable from Python.
- `QgsLayerStylingWidget` drives its undo stack by serialising
  `writeStyle()` into a `QDomDocument` and comparing
  (`qgslayerstylingwidget.cpp:338-343`, `pushUndoItem`).

Comparing content rather than trusting notification fixes three problems at
once: it closes the labeling hole, it makes the spurious emitters harmless
because they do not change serialised content, and it collapses the
colour-wheel storm to a single state transition.

The ordering constraint at `layer_manager.py:551-552` and `:487-488` —
`loadNamedStyle` before `attach_dirty_tracking` — is **preserved and becomes
load-bearing for a new reason**. The baseline is captured inside
`attach_dirty_tracking`, so a sidecar applied after attach would change the
serialised style relative to that baseline and mark a freshly opened layer
dirty. An earlier draft of this decision claimed fingerprinting made the
ordering irrelevant; that was wrong. Both call sites carry a comment and a
regression test instead.

## Alternatives rejected

- **Switch to `rendererChanged`.** Strictly narrower than `styleChanged`;
  measured at zero emissions for in-place symbol mutation.
- **Switch to `repaintRequested` alone, without a fingerprint.** Fires on data
  edits, selection changes and refresh timers, so it would mark almost
  everything style-dirty.
- **Add missing `emitStyleChanged()` calls upstream in QGIS.** Correct in
  principle but unavailable on our release timeline, and it would leave the
  plugin broken on every QGIS version already in the field.
- **Poll on a timer.** Equivalent accuracy at much higher idle cost, with no
  natural trigger to bound the work.

## Consequences

- The baseline is held **in memory only**, in a module-level dict keyed by
  layer id, with entries removed on `layer.destroyed`. Storing it in a QGIS
  custom property would persist the hash into the `.qgs` file, churn the
  project on every style edit, and entangle with the deferred KI-008.
- The dirty property is written only on a clean → dirty transition. Comparing
  against the original baseline keeps reporting a difference after the layer
  is already dirty, so an unconditional write would recreate the
  badge-recompute storm this decision exists to remove.
- `writeStyle()` serialises to XML on each debounced check. Bounded by the
  debounce and by applying it only to Rana-linked layers, but worth a sanity
  check on projects with many layers.
- Re-baselining on sync is easy to forget and produces a confusing
  re-dirty-immediately bug if missed; it needs an explicit test.
- Existing tests that emit `styleChanged` without mutating the style become
  invalid by construction and must be migrated to real style changes.
- Timers must be parented to the layer so they die with it. The existing
  lambdas in `dirty_tracking.py` already hold a strong reference to `layer`,
  keeping the Python wrapper alive after the C++ object is deleted; that
  cycle should be fixed here rather than duplicated.
- Data dirtiness is unaffected — `afterCommitChanges` remains the mechanism
  for vectors, and raster data remains `UNKNOWN` until raster tracking is
  implemented (KI-007).
