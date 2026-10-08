# Decision: Project Visibility Blocklist vs Allowlist

**Date:** 2026-08-03  
**Status:** Accepted  
**Feature:** feat_425_project_selector

## Decision

Store a **blocklist** of hidden project IDs per `(base_url, tenant_id)` scope.

## Options Considered

**A. Blocklist (chosen)** — store IDs of hidden projects  
**B. Allowlist** — store IDs of shown projects

## Rationale

- An empty blocklist means "show everything" — correct default for new users, no setup required
- New projects added server-side appear automatically, which matches expected browser behavior
- Users typically hide a small number of projects, so storage is minimal
- An allowlist would require explicit opt-in for every project and break on newly added projects

## Consequences

- Stale entries (deleted projects) linger harmlessly in the blocklist and are silently ignored
- No periodic cleanup is needed
