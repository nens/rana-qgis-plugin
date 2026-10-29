---
type: decision
id: 20261029-1300-processes-notify-on-process-start
date: 2026-10-29
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/loader.py
  - rana_qgis_plugin/widgets/version_history_dialog.py
  - rana_qgis_plugin/widgets/processes_panel.py
tags: [processes, notifications, simulation, model-creation]
participants: [engineer, assistant]
---

# Point the user at the Processes window when a process is started elsewhere

## Context

`SchematisationRevisionHistoryDialog` (via `Loader.start_simulation` and
`Loader.start_model_tracker_process`) already starts Rana tracker processes
and today shows the user a blocking `QMessageBox.information` with one or
more `<a href>` links to track progress on the Rana web app:
- `create_model` (`version_history_dialog.py:631-652`): single job id, via
  the dialog-local `show_process_url_popup`.
- `Loader.start_simulation_tracker_process` (`loader.py:573-629`): one or
  more job ids (one per simulation, for the "multiple simulations" case),
  built and shown directly inside `Loader`.

Now that a Processes window exists, the user wants these flows to point at
it instead of the external-link popup, which is now considered obsolete and
should not be shown at all, not even as a fallback:
- dock open and floating → bring it to the front.
- dock open and docked → "nothing, or is there a way to highlight it."
- dock not open → ask the user whether to open it.
- once visible, highlight the specific new row(s).

This revises a prior "Out of Scope" line in the design
(`20261029-1105`-era: "Automatically opening/notifying from this window when
a job starts or finishes while it is closed") — that exclusion was about
unsolicited background notifications; this decision is narrower: a direct,
synchronous consequence of an action the user just took in the same
session, not a background watcher.

## Options Considered

### Option 1: Keep the existing link popups unchanged

Leave `create_model`/`start_simulation_tracker_process` as they are.
- ✅ No new code.
- ❌ Ignores the explicit request; the Processes window (once it exists)
  would be an obviously better destination than an external web link for a
  job the user can now watch live, in-app.

### Option 2: Dock-aware notification, falling back to the existing popup

Add a shared `Loader.point_user_to_processes(project, job_ids, error_signals, parent) -> bool`
that raises/highlights an open dock, or asks to open one; callers show
their existing link popup only when this returns `False` (user declined).
- ✅ Reuses the dock registry and `ProcessesPanel` already being built; no
  new window type.
- ❌ Keeps the external-link popup alive as dead-weight UX the user
  explicitly considers obsolete — rejected.

### Option 3: Dock-aware notification, no fallback; a plain "started" message replaces the popup entirely

Same `point_user_to_processes`, but with no return value callers branch on,
and the external-link popup (and the code that builds it) is deleted
outright. A plain, link-free confirmation (`communication.bar_info`, no
`<a href>`) is given unconditionally as soon as the tracker job(s) are
successfully started — independent of whether the dock gets raised,
docked-nudged, or the user declines to open it — so declining the "open
Processes?" prompt never leaves the user without feedback that something
happened; it just means they don't also get pointed at the window this time.
- ✅ Matches the explicit instruction: the link popup is gone, not just
  deprioritized.
- ✅ Simpler: `point_user_to_processes` no longer needs a return value or
  any caller-side branching on it.
- ✅ `create_model` already gets this via `start_model_tracker_process`'s
  existing unconditional `bar_info("Revision uploaded; model creation
  started.")` — no new message needed there, only `start_simulation_tracker_process`
  needs one added (it currently has no success feedback at all besides the
  now-removed popup).
- ❌ Still requires the same `error_signals` threading as Option 2.

## Decision

Chosen: **Option 3**. Add `Loader.point_user_to_processes(project: dict, job_ids: list[str], error_signals: ApiErrorSignals, parent=None) -> None`:

- **Dock open and floating**: `dock.raise_()` + `dock.activateWindow()` —
  brings the free-floating window to the front of other windows.
- **Dock open and docked**: `dock.raise_()` (Qt brings a tabified dock
  widget's tab to the front; a no-op if it's already the sole visible
  panel in its area) **plus** `communication.bar_info("See the Processes
  panel for progress.")` as a low-friction nudge, since a raise alone may
  be invisible if the panel was already the frontmost tab. No custom
  flashing/animation — that would be meaningfully more UI code for a
  problem a one-line message bar notice already solves well enough.
- **Dock not open**: `communication.ask(parent, "Processes", "Track
  progress in the Processes window?")`; if confirmed, call the existing
  `open_processes_dock` and highlight; if declined, do nothing further —
  no fallback popup. The unconditional "started" message (below) already
  told the user their job is running.
- In both "open" paths, call `dock.widget().highlight_jobs(job_ids)`.

Each caller gives its own unconditional, link-free "started" confirmation
before calling `point_user_to_processes`, independent of its outcome:
- `create_model`: already covered by `start_model_tracker_process`'s
  existing `bar_info("Revision uploaded; model creation started.")` — no
  change needed there.
- `start_simulation_tracker_process`: add `communication.bar_info(...)`
  (e.g. "N simulation(s) started.") once tracker jobs are successfully
  created, replacing the removed `<a href>`-building `links` list and its
  final `QMessageBox.information` entirely. `show_process_url_popup`
  (`version_history_dialog.py`) is deleted outright, not kept as a fallback.

Add `ProcessesPanel.highlight_jobs(job_ids: list[str])`: record the
requested ids; if a fetch is already in flight (e.g. the dock's own
just-triggered initial fetch), wait for it rather than starting a second,
redundant one; otherwise trigger an immediate fetch (reusing the
fetch-now/coalescing path already built for filter changes). Once a fetch completes,
check the requested ids against the refreshed rows: if found, select +
scroll to them and call `JobsTableModel.set_highlighted_job_ids(...)`
(temporary `Qt.BackgroundRole` override), clearing it via a single-shot
30-second `QTimer` (adjusted after UI review to give users more time to locate
the highlighted row). If a job still
isn't present (e.g. excluded by an active status/text filter), do nothing
further for v1 — filters are not auto-cleared, since that would be a
surprising side effect of an action the user didn't take; documented as a
known limitation.

Scope: only `SchematisationRevisionHistoryDialog`'s `create_model` and the
`start_simulation` → `start_simulation_tracker_process` chain are wired to
this. The initial-revision-upload flow's own `start_model_tracker_process`
call (`loader.py:892-902`) already discards its response and shows no
popup at all today — left as a noted, pre-existing gap, not silently
folded into this feature's scope.

## Consequences

### Positive
- ✅ Directly answers the request: floating → front, docked → raised tab +
  nudge, not-open → asked, and the new row(s) are highlighted once visible.
- ✅ Removes the obsolete external-link popup entirely, including the
  dead-code `show_process_url_popup` method and the `<a href>`-building
  `links` list in `start_simulation_tracker_process`.
- ✅ Reduces blocking popups for the already-open-dock case versus today's
  behavior (always a modal), rather than adding a new one.
- ✅ Reuses the dock registry, `open_processes_dock`, and the fetch-now
  mechanism already designed — no new window or task type.
- ✅ Simpler interface: `point_user_to_processes` has no return value for
  callers to branch on.

### Negative
- ⚠️ Threading `error_signals` through 3 existing simulation-flow method
  signatures is mechanical but touches code outside this feature's own
  new files.
- ⚠️ A highlighted job excluded by the panel's current filters won't be
  visually found; only documented, not auto-fixed, for v1.
- ⚠️ `dock.raise_()` on an already-frontmost, non-tabified dock is a
  visual no-op; the `bar_info` nudge is the only cue in that specific case.
- ⚠️ A user who declines to open the dock and doesn't notice the message
  bar has no other way to find the job from this flow (acceptable: they
  can still reach it via the project's **Processes** context-menu action).

## Code References

- Existing popups being removed outright (not kept as fallback): `rana_qgis_plugin/widgets/version_history_dialog.py:631-652` (`create_model`, `show_process_url_popup` — method deleted), `rana_qgis_plugin/loader.py:573-629` (`start_simulation_tracker_process` — `links`/`escape`/`get_rana_processes_url` usage removed)
- Simulation call chain needing `error_signals` threaded through: `rana_qgis_plugin/loader.py:452` (`start_simulation`), `:200` (`start_simulations`), `:237` (the `initializing_simulations_finished` lambda)
- Noted, out-of-scope gap: `rana_qgis_plugin/loader.py:892-902` (initial revision upload's `start_model_tracker_process` call, response already discarded today)
- Confirmation dialog helper (existing): `rana_qgis_plugin/communication.py:72` (`UICommunication.ask`)
- Dock registry this builds on: `20261029-1105-processes-window-container`
- Fetch-now/coalescing mechanism this reuses: `20261029-1106-processes-background-polling`

## Related Decisions

- `20261029-1105-processes-window-container`
- `20261029-1106-processes-background-polling`

## Notes

This narrows, not contradicts, the design's earlier "no automatic
notifications when the window is closed" exclusion — that was about
unsolicited background watching; this is a direct, same-session
consequence of an action the user just took, gated by an explicit
confirmation when no dock is open.
