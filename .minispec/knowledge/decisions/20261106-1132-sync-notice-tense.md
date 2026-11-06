---
type: decision
id: 20261106-1132-sync-notice-tense
date: 2026-11-06
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/layer_management/sync_summary.py
  - rana_qgis_plugin/layer_management/layer_tree_menu.py
tags: [sync, messaging]
participants: [engineer, build agent]
---

# Present-Tense "Syncing ..." Notice for Sync-on-Demand

## Context
The on-demand notice is shown right after dispatch, and the upload is still running when
it appears.

## Decision
Use present tense: "Syncing <name> to Rana...". Past tense ("Synced") would claim
completion that has not happened yet.

## Consequences
- The notice does not block or cancel the upload. It is shown immediately, and
  dispatch does not wait for it.
- The notice is a non-blocking dialog; see `20261106-1240-sync-prompt-dialog`.
