---
type: decision
id: 20261125-1010-sim-result-destination-path-semantics
date: 2026-11-25
status: accepted
supersedes: null
superseded_by: null
impacts:
  - rana_qgis_plugin/simulation/simulation_wizard.py
  - rana_qgis_plugin/loader.py
tags: [simulation, wizard, results, destination, paths]
participants: [margriet, agent]
---

# Typed and picked simulation result destination paths

## Context

Users can type the destination or pick it with a Rana folder picker. Typed
input may come from Windows users (`\`), may contain spaces, and must never
point outside the Rana project. The picker opens in the schematisation folder
and cannot go above the project root.

## Options Considered

- Relative to the schematisation folder only (no going upwards): simplest, but
  cannot reach sibling folders.
- Project-relative path pre-filled with the schematisation folder: shows the
  real path, but "optional" becomes awkward.
- **Both relative and absolute, relative by default** (chosen).

## Decision

Applies to phase 2 (typed input). Phase 1 only has a picker and needs no path
parsing (see `20261125-1020-sim-result-destination-field-ux`).

Typed input:

| Input | Meaning |
|---|---|
| empty | schematisation folder (current behaviour) |
| `results`, `./results`, `.\results` | `<schematisation folder>/results/` |
| `/shared/results`, `\shared\results` | `<project root>/shared/results/` |
| `../shared` | resolved; error if it goes above the project root |
| `C:\…`, `\\server\…` | rejected: not a Rana project path |

Normalisation: `\` → `/`; empty and `.` segments dropped; whitespace around
each segment trimmed; spaces inside names kept; `..` resolved and bounded by
the project root.

Picker output: a selected folder below the schematisation folder is written as a
relative path (`results/sub`). Any other folder is written as an absolute path
(`/shared/results`).

## Consequences

- One pure function resolves (schematisation folder, typed text) → project path
  or error. It can be unit tested without Qt or the network.
- The project root is always reachable via `/`, so `..` is a convenience, not a
  requirement.
