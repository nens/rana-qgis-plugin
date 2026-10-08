# Decision: Extract a shared "process link popup" helper

**ID:** 20261001-1400-simulation-popup-helper-dedup
**Date:** 2026-10-01
**Status:** Accepted

## Context

`create_model` (in `version_history_dialog.py`, calling into
`Loader.start_model_tracker_process`) already builds a
`QMessageBox.information(... f'<a href="{url}">Track model creation in
Rana</a>')` using `get_rana_processes_url(project_slug, job_id)`. The new
simulation flow needs the same popup, potentially with multiple links (see
`20261001-1400-simulation-multi-result-popup`).

## Decision

Extract a shared `Loader.show_process_link_popup(parent, title, project_slug, links)`
helper (`links` being a list of `(label, job_id)` pairs), used by both
`create_model`'s existing popup and the new simulation popup(s).

## Reasoning

- Avoids duplicating the `QMessageBox` + URL-building block for a second
  near-identical use.
- Keeps the single-link Create Model case trivially simple (pass a
  one-item list) while directly supporting the simulation
  multi-link case.

## Consequences

`create_model` is edited to call the new helper instead of its inline
`QMessageBox.information` call, as a small refactor alongside this feature.
