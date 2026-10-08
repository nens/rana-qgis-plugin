# Decision: Use QgsDataItemGuiProvider for inline rename

**Date:** 2026-08-14
**Status:** Superseded by [20260817-0903-rename-via-dialog-supersedes-gui-provider](20260817-0903-rename-via-dialog-supersedes-gui-provider.md)

## Context

We need a rename UI for files and folders in the Rana browser tree. Two approaches were considered:

1. **QgsDataItem.rename()** — virtual method on the item itself. Supports native inline rename (F2/slow double-click). However, this method is deprecated since QGIS 3.10 in favor of `QgsDataItemGuiProvider`.

2. **Dialog-based rename via existing QAction** — wire the already-defined `RENAME` QAction to a `QInputDialog.getText()` handler. Zero new classes, fits the existing `actions()`-based pattern. No deprecated APIs.

3. **QgsDataItemGuiProvider.rename()** — the non-deprecated replacement. Requires a new `QgsDataItemGuiProvider` subclass registered with `QgsGui.dataItemGuiProviderRegistry()`. Items declare `Qgis.BrowserItemCapability.Rename`; QGIS handles the inline editing UI automatically.

## Decision

Use `QgsDataItemGuiProvider.rename()` (option 3).

## Reasoning

- Avoids deprecated `QgsDataItem.rename()` API, future-proofing for QGIS 5.x
- Native inline rename (F2 / slow double-click) is a better UX than a dialog
- The new provider class is small (~40-60 lines) and isolated — it introduces a new pattern but doesn't conflict with the existing `actions()`-based context menus used for other operations
- Registration/unregistration is 2 lines in plugin lifecycle

## Risks

- The exact QGIS dispatch logic for which provider's `rename()` is invoked for a given item isn't fully documented. A quick spike should verify the mechanism before full implementation.
- Must unregister the provider on plugin `unload()` to avoid stale references across plugin reloads.
