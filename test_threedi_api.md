# Minimal UI Test Paths for threedi-api-client Backwards Compatibility

## Progress
- [ ] Path 1: Browse & Discover
- [ ] Path 2: Upload New Schematisation
- [ ] Path 3: Create Simulation (Full Wizard)
- [ ] Path 4: Create Simulation from Template
- [ ] Path 5: Monitor & Download Results
- [ ] Path 6: Schematisation Download/Export
- [ ] Path 7: Model Management
- [ ] Path 8: Template Management
- [ ] Path 9: Initial Concentrations with Raster Upload
- [ ] Path 10: Contracts & Organizations

## Path 1: Browse & Discover (Read Operations)
**Steps:** Open the file browser and click/select a schematisation (opens revisions / file view)

### Checklist
- [x] Path 1: Browse & Discover
  - [x] `schematisations_revisions_list()` — triggered when clicking a schematisation in the file browser (opens revisions view)
  - [x] `schematisations_revisions_threedimodels()` — triggered when selecting a schematisation in the file view panel

---

## Path 2: Upload New Schematisation + Create Model
**Steps:** File browser → "Upload new schematisation" → fill name/org → select geopackage with rasters → Finish → monitor task

### Checklist
- [ ] Path 2: Upload New Schematisation + Create Model
  - [x] `schematisations_create()`
  - [x] `organisations_list()` — called when upload/wizard is initiated
  - [x] `schematisations_revisions_create()`
  - [x] `schematisations_revisions_sqlite_upload()`
  - [x] `schematisations_revisions_rasters_create()` + `_upload()` (per raster)
  - [x] `schematisations_revisions_rasters_list()` — check existing rasters during upload wizard

## Path 3: create model

  - [x] `threedimodels_list()` — model listing used in upload / model selection or deletion dialog
  - [x] `schematisations_revisions_commit()`
  - [x] `schematisations_revisions_create_threedimodel()`
  - [x] `auth_profile_list()` — triggered when "create 3Di model" option is selected after upload

---

## Path 3: Create Simulation (Full Wizard — max options)
**Steps:** Simulation wizard → select model → configure ALL optional pages → Finish

### Checklist
- [ ] Path 3: Create Simulation (Full Wizard)
  - [x] `organisations_list()` — called when upload/wizard is initiated
  - [x] 3a. Model selection: `threedimodels_list()` (with search/filter)
  - [ ] 3b. Initial Conditions page load:
    - [ ] `threedimodels_saved_states_list()`
    - [ ] `threedimodels_initial_waterlevels_list()` / `_read()`
    - [ ] `threedimodels_rasters_list()` / `_read()`
    - [ ] `threedimodels_initial_concentrations_list()`
    - [ ] `threedimodels_potentialbreaches_list()` / `_read()`
  - [ ] 3c. On Finish (SimulationRunner):
    - [ ] `simulations_create()`
    - [ ] `simulations_substances_create()`
    - [ ] `simulations_events_boundaryconditions_file_create()`
    - [ ] `simulations_events_structure_control_file_create()` (or `_memory`, `_table`, `_timed`)
    - [ ] `simulations_initial1d_water_level_constant_create()` (or `_predefined`, `_file`)
    - [ ] `simulations_initial2d_water_level_constant_create()` (or `_raster`)
    - [ ] `simulations_initial_groundwater_level_constant_create()` (or `_raster`)
    - [ ] `simulations_initial1d_substance_concentrations_create()`
    - [ ] `simulations_initial2d_substance_concentrations_create()`
    - [ ] `simulations_initial_saved_state_create()`
    - [ ] `simulations_events_lateral_constant_create()` (or `_timeseries`, `_file`)
    - [ ] `simulations_events_rain_constant_create()` (or `_timeseries`, `_rasters_netcdf`, `_rasters_lizard`, `_timeseries_lizard`, `_timeseries_netcdf`, `_local_constant`, `_local_timeseries`)
    - [ ] `simulations_events_wind_constant_create()` (or `_timeseries`)
    - [ ] `simulations_initial_wind_drag_coefficient_create()`
    - [ ] `simulations_events_breaches_create()`
    - [ ] `simulations_events_raster_edits_create()`
    - [ ] `simulations_events_obstacle_edits_create()`
    - [ ] `simulations_events_sources_sinks_*_create()`
    - [ ] `simulations_settings_physical_create()`
    - [ ] `simulations_settings_numerical_create()`
    - [ ] `simulations_settings_time_step_create()`
    - [ ] `simulations_settings_aggregation_create()`
    - [ ] `simulations_settings_water_quality_create()`
    - [ ] `simulations_settings_output_settings_create()`
    - [ ] `simulations_create_saved_states_timed_create()` (or `_stable_threshold`)
    - [ ] `simulations_results_post_processing_lizard_basic_create()` (or `_arrival`, `_damage`)
    - [ ] `simulations_actions_create()` — queues simulation
    - [ ] `threedimodels_tasks_list()` / `_read()` — poll raster processing task (only when initial conditions include a locally-uploaded raster: 2D water level, groundwater, or concentration)

---

## Path 4: Create Simulation from Template
**Steps:** Simulation wizard → "From template" → select template → adjust parameters → Finish

### Checklist
- [ ] Path 4: Create Simulation from Template
  - [ ] `simulation_templates_list()`
  - [ ] `simulation_templates_read()`
  - [ ] `simulations_events()` — fetches template event data
  - [ ] `simulations_settings_overview()` — fetches template settings
  - [ ] `simulations_events_lateral_file_list()` / `_read()` / `_download()`
  - [ ] `simulations_events_boundaryconditions_file_list()` / `_read()` / `_download()`
  - [ ] `simulations_events_structure_control_file_list()` / `_read()` / `_download()`
  - [ ] `simulations_from_template()` — creates sim from template

---

## Path 5: Monitor Simulation & Download Results
**Steps:** Simulations browser → select running simulation → wait for completion → download results

### Checklist
- [ ] Path 5: Monitor Simulation & Download Results
  - [ ] `simulations_list()`
  - [ ] `simulations_read()`
  - [ ] `simulations_status_list()`
  - [ ] `simulations_progress_list()`
  - [ ] `statuses_list()`
  - [ ] `simulations_results_files_list()`
  - [ ] `simulations_results_files_download()`
  - [ ] `threedimodels_gridadmin_download()`
  - [ ] `threedimodels_geopackage_download()`
  - [ ] `simulations_results_post_processing_lizard_overview_list()`

---

## Path 6: Schematisation Download/Export
**Steps:** File browser → right-click schematisation revision → "Download"

### Checklist
- [ ] Path 6: Schematisation Download/Export
  - [ ] `schematisations_revisions_sqlite_download()`
  - [ ] `schematisations_revisions_rasters_download()`

---

## Path 7: Model Management (Context Menu)
**Steps:** File browser → right-click model → "Delete model" / "Create model from revision"

### Checklist
- [ ] Path 7: Model Management
  - [ ] `threedimodels_delete()`
  - [ ] `schematisations_revisions_create_threedimodel()` (with `inherit_templates` flag)

---

## Path 8: Template Management
**Steps:** After simulation completes → "Save as template" / Delete existing template

### Checklist
- [ ] Path 8: Template Management
  - [ ] `simulation_templates_create()`
  - [ ] `simulation_templates_delete()`

---

## Path 9: Initial Concentrations with Raster Upload
**Steps:** Simulation wizard → Initial Conditions → add initial concentration → upload 2D raster

### Checklist
- [ ] Path 9: Initial Concentrations with Raster Upload
  - [ ] `threedimodels_initial_concentrations_list()`
  - [ ] `threedimodels_rasters_create()` + `_upload()`
  - [ ] `threedimodels_tasks_read()` — poll upload task

---

## Path 10: Contracts & Organizations
**Steps:** Login / any operation that checks contract limits

### Checklist
- [ ] Path 10: Contracts & Organizations
  - [ ] `contracts_list()`
  - [ ] `repositories_list()`
  - [ ] `revisions_list()` / `revisions_threedimodels()`

---

## Summary Matrix

| Path | Main Feature | Distinct Endpoints |
|------|-------------|------|
| 1 | Browse & discover | ~8 |
| 2 | Upload schematisation | ~6 |
| 3 | Full simulation wizard | ~40+ |
| 4 | Simulation from template | ~10 |
| 5 | Monitor & download results | ~8 |
| 6 | Schematisation download | ~2 |
| 7 | Model CRUD | ~2 |
| 8 | Template management | ~2 |
| 9 | Concentration raster upload | ~3 |
| 10 | Contracts/orgs | ~3 |

**Paths 1–5 cover ~90% of all distinct endpoints.** Paths 6–10 cover edge cases and secondary flows.

## Testing Priority

1. **Start with Path 1** — if browse/list calls fail, nothing else works
2. **Path 3 (partial)** — create a simple simulation (constant rain, no events) to test creation
3. **Path 5** — verify results download still works
4. **Path 2** — upload flow exercises the write side
5. **Path 4** — template flow exercises the "from_template" codepath which is a different endpoint
