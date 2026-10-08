# Decision: Project Visibility Storage — JSON File

**Date:** 2026-08-03  
**Status:** Accepted  
**Feature:** feat_425_project_selector

## Decision

Store hidden project IDs in a JSON file at `{qgisSettingsDirPath}/rana/hidden_projects.json`, not in `QgsSettings`.

## Options Considered

**A. QgsSettings** — serialized JSON string per namespaced key  
**B. JSON file (chosen)** — dedicated file in QGIS profile directory

## Rationale

- A user with many hidden projects would produce a very long QgsSettings value, cluttering the settings registry
- A dedicated file is easier to inspect, debug, and reason about
- The file lives in the QGIS profile directory (not `rana_cache_dir`) so it is not deleted when the user clears the download cache
- Atomic writes (write to `.tmp`, rename) make concurrent reads safe from the background `createChildren()` thread

## Key Details

- File location: `Path(QgsApplication.qgisSettingsDirPath()) / "rana" / "hidden_projects.json"`
- JSON structure: `{ "{base_url}|{tenant_id}": ["id1", "id2"] }`
- Missing file → empty hidden set (no error)
- Writes are atomic to prevent corruption from concurrent access
