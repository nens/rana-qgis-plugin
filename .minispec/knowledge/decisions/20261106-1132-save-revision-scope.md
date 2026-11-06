---
type: decision
id: 20261106-1132-save-revision-scope
date: 2026-11-06
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [sync, scope]
participants: [engineer, build agent]
---

# Exclude "Save revision" From the Change Summary

## Context
"Save revision" uploads a single schematisation database for a revision. It is not
a list of changed layers or files.

## Decision
Leave `save_revision` out of this feature. It gets no change-summary notice.

## Consequences
- Only sync-on-demand (style and data), sync-on-layer-close, and
  sync-on-project-close show a summary.
