# Decision: Marker in QML File vs. Pass-Through Flag

**Date:** 2026-04-24  
**Status:** Accepted  
**Context:** Physical quantity style rescaling feature needs to track whether a raster's QML was generated from `physical_quantity.qml` (needs rescaling) or user-uploaded (use as-is).

## Problem

Two candidates emerged:
1. **Option A: Comment marker in QML file** — Prepend `<!-- rana:physical_quantity_style -->` to the QML at download time, detect at load time by reading the file
2. **Option B: Pass-through flag** — Thread a boolean flag through signatures: `postprocess()` → `on_file_download_finished()` → `open_file_via_layer_manager()` → `add_from_file()` → `_add_layer_from_raster_file()`

## Decision: Option A (Marker in QML File)

### Reasoning

| Aspect | Option A | Option B |
|--------|----------|----------|
| **Separation of Concerns** | Good — download marks what it did; load uses the mark. Loader is unaware of download's source. | Couples loader to download flow; loader must know its origin. |
| **Signature Changes** | None — no function signatures modified. | Requires threading flag through 4 call sites across multiple modules. |
| **Persistence on Re-upload** | Safe — comment stays local; style upload regenerates QML from in-memory state, never reads the local file. | N/A — no persistence risk. |
| **Simplicity** | Simple: one-liner to add comment, one-liner to detect. | More complex: flag must flow through and be preserved. |

### Implementation

**Download time (`workers/download.py`):**
```python
def _handle_raster_qml_files(self):
    pq_path = self.download_context.local_dir / "physical_quantity.qml"
    if pq_path.exists():
        new_name = self.download_context.local_file_path.with_suffix(".qml").name
        pq_path.rename(self.download_context.local_dir / new_name)
        # Mark the file so load-time can detect it's a physical_quantity style
        qml_path = self.download_context.local_dir / new_name
        qml_path.write_text(
            "<!-- rana:physical_quantity_style -->\n" + qml_path.read_text()
        )
```

**Load time (`layer_manager.py`):**
```python
qml_path = Path(local_file_path).with_suffix(".qml")
if qml_path.exists() and "rana:physical_quantity_style" in qml_path.read_text(limit=200):
    # Rescale renderer
    ...
```

### Trade-offs Accepted

- Comment adds ~60 bytes to QML file (negligible)
- Must read first ~200 bytes of QML file at load time (fast, minimal I/O)
- If user manually edits the QML file externally and removes the comment, rescaling won't trigger (acceptable; they edited it intentionally)

## Alternatives Considered & Rejected

**Option B (Pass-through flag):** More coupling, more signature changes, no safety advantage.

**Option C (Heuristic detection at load time):** Detect physical_quantity by file location or naming convention. Rejected because:
- Both `physical_quantity.qml` and user-uploaded `<filename>.qml` are renamed to `<filename>.qml`, making heuristic impossible
- User-uploaded and backend-generated files would be indistinguishable

## Approval

Discussed with Margriet. Approved as part of overall design conversation.
