# DETAILED PAGINATION AUDIT: Complete Call Site Analysis

## Overview
This document provides complete line-by-line analysis of every call site for the 6 pagination-vulnerable functions.

---

## FUNCTION 1: get_user_tenants (Line 155)

### Function Definition
```python
def get_user_tenants(communication: UICommunication, user_id: str):
    authcfg_id = get_authcfg_id()
    url = f"{api_url()}/tenants"
    params = {"user_id": user_id}
    
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)  # <-- NO pagination
    
    if status:
        response = network_manager.content
        items = response["items"]  # <-- Returns only first page
        return items
```

### Call Site 1: rana_qgis_plugin.py:223

**Full Context (lines 213-231)**:
```python
if show_authentication:
    authcfg_id = get_authcfg_id()
    if authcfg_id:
        user = get_user_info(self.communication)
        if user:
            user_id = user["sub"]
            user_name = f"{user['given_name']} {user['family_name']}"
            user_action = QAction(user_name, self.iface.mainWindow())
            user_action.setEnabled(False)
            menu.addAction(user_action)
            self.tenants = get_user_tenants(self.communication, user_id)  # <-- CALL
            if len(self.tenants) > 1:  # <-- VALIDATION ISSUE
                switch_tenant_action = QAction(
                    "Switch Organisation", self.iface.mainWindow()
                )
                switch_tenant_action.triggered.connect(
                    self.open_tenant_selection_dialog
                )
                menu.addAction(switch_tenant_action)
```

**Data Flow**:
1. User logs in
2. `get_user_tenants()` fetches from `/tenants?user_id={user_id}`
3. **Returns only first page** (no limit specified, uses API default)
4. Check `if len(self.tenants) > 1` determines if "Switch Organisation" menu appears
5. Users with 100+ tenants: menu shows switch option, but can't actually switch to 101+

**Impact**:
- **Critical**: Multi-tenant functionality broken for large organizations
- User sees "Switch Organisation" menu but cannot access all organizations
- Only organizations 1 through API_DEFAULT_LIMIT available

---

## FUNCTION 2: get_tenant_projects (Line 188)

### Function Definition
```python
def get_tenant_projects(communication: UICommunication):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects"
    params = {"limit": 1000}  # <-- Hardcoded 1000
    
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)
    
    if status:
        response = network_manager.content
        items = response["items"]  # <-- First 1000 only
        return items
```

### Call Site 2A: projects_browser.py:171

**Function Context**: `fetch_projects()`
```python
def fetch_projects(self):
    self.tenant_projects = get_tenant_projects(self.communication)  # <-- CALL
```

**Called From**: `refresh()` method (line 183)
```python
def refresh(self):
    self.current_page = 1
    self.fetch_projects()  # <-- CALL
    self.update_users()
    self.sort_projects(2, Qt.SortOrder.AscendingOrder, populate=False)
    if self.filter_active:
        self.filter_projects()
    else:
        self.populate_projects()
    self.populate_contributors()
    self.projects_refreshed.emit()
```

**Impact**: Sets `self.tenant_projects` used throughout the class

### Call Site 2B: projects_browser.py:177-180

**Function Context**: `update_users()`
```python
def update_users(self):
    self.users = list(
        {
            contributor["id"]: contributor
            for project in self.tenant_projects  # <-- USES INCOMPLETE DATA
            for contributor in project["contributors"]  # <-- MISSING 1001+ PROJECTS
        }.values()
    )
    self.users_refreshed.emit(self.users)
```

**Impact**: 
- Contributor list is incomplete
- Missing contributors from projects 1001+
- UI contributor filter shows incomplete list

### Call Site 2C: projects_browser.py:229

**Function Context**: `get_projects_filtered_by_name()`
```python
def get_projects_filtered_by_name(self):
    text = self.projects_search.text()
    if text:
        return [
            project
            for project in self.tenant_projects  # <-- INCOMPLETE DATA
            if text.lower() in project["name"].lower()  # <-- SEARCHES ONLY 1-1000
        ]
    else:
        return self.tenant_projects
```

**Called From**: `filter_projects()` (line 206-221)
```python
def filter_projects(self):
    if not self.filter_active:
        self.filtered_projects = self.tenant_projects
    else:
        # create all filters
        project_filters = [
            self.get_projects_filtered_by_name,  # <-- CALL
            self.get_projects_filtered_by_contributor,
        ]
        # collect all project ids that are included in each active filter
        project_ids = [
            {project["id"] for project in filter_func()}
            for filter_func in project_filters
        ]
        # Find project ids that are included in all filters
        common_ids = set.intersection(*project_ids)
        self.filtered_projects = [
            project
            for project in self.tenant_projects
            if project["id"] in common_ids
        ]
    self.populate_projects()
```

**Impact**:
- User searches for project "test" expecting all matching projects
- If project "test_1250" exists but exceeds 1000 limit
- Search returns: "Not found" (but project exists on server)
- User has no idea project exists

### Call Site 2D: projects_browser.py:249-268

**Function Context**: `sort_projects()`
```python
def sort_projects(self, column_index: int, order: Qt.SortOrder, populate=True):
    def sort_key_function(project):
        column_names = ["name", "created_at", "description"]
        # sorting logic that uses all projects
    
    # sort self.filtered_projects which comes from self.tenant_projects
```

**Impact**: Sorting UI may be incomplete

---

## FUNCTION 3: get_tenant_project_files (Line 206)

### Function Definition
```python
def get_tenant_project_files(
    communication: UICommunication, project_id: str, params: dict = None
):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/projects/{project_id}/files/ls"
    
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)  # <-- Caller specifies limit
    
    if status:
        response = network_manager.content
        items = response["items"]  # <-- Only one page returned
        return items
```

### Call Site 3A: files_browser.py:251-256

**Function Context**: `fetch_and_populate()`
```python
def fetch_and_populate(self, project: dict, path: str = None):
    params = {"limit": 1000}  # <-- Caller sets limit
    if path:
        params["path"] = path
    self.files = get_tenant_project_files(self.communication, project["id"], params)  # <-- CALL
    sort_column = self.files_tv.header().sortIndicatorSection()
    sort_order = self.files_tv.header().sortIndicatorOrder()
    
    # Then uses self.files for UI population
    directories = [file for file in self.files if file["type"] == "directory"]  # <-- INCOMPLETE
    files = [file for file in self.files if file["type"] == "file"]  # <-- INCOMPLETE
```

**Called From**: User selects file/directory in UI (line 240)
```python
def select_file_or_directory(self, index: QModelIndex):
    self.busy.emit()
    self.communication.progress_bar("Loading files...", clear_msg_bar=True)
    if index.column() != 0:
        return
    file_item = self.files_model.itemFromIndex(index)
    self.selected_item = file_item.data(Qt.ItemDataRole.UserRole)
    self.update()  # <-- Calls fetch_and_populate indirectly
    self.ready.emit()
```

**Impact**:
- Files browser only shows first 1000 files/folders
- User cannot navigate beyond 1000 items
- Silent data truncation

### Call Site 3B: loader.py:398-404

**Function Context**: `rename_item_on_rana()` - CRITICAL VALIDATION BUG
```python
def rename_item_on_rana(self, project, item, new_name: str):
    """Rename file or directory with duplicate detection."""
    source_path = item["id"]
    target_path = source_path.rsplit("/", 1)[0] + "/" + new_name
    
    if file["type"] == "directory":
        # check for duplicates
        if len(Path(source_path).parents) > 1:
            root_path = Path(source_path).parent.as_posix()
        else:
            root_path = None
        names = [
            file["id"].strip("/")
            for file in get_tenant_project_files(  # <-- CALL
                self.communication,
                project["id"],
                params={"path": root_path} if root_path else None,
            )
            if file["type"] == "directory"
        ]
        if new_name in names:  # <-- VALIDATION DEPENDS ON COMPLETE LIST
            QMessageBox.warning(
                self.parent(), "Warning", f"Folder {new_name} already exists."
            )
            return  # <-- Abort move if duplicate found
```

**CRITICAL BUG SCENARIO**:
```
Directory structure:
  - Item 1-999: Various files
  - Item 1250: Folder named "duplicate"
  - Item 1251-1500: More files

get_tenant_project_files() returns items 1-1000 (due to limit=1000)
Item 1250 "duplicate" is NOT in the returned list

User tries to rename Item 500 to "duplicate":
  1. Function fetches file list (gets items 1-1000)
  2. Searches for "duplicate" in returned items
  3. "duplicate" NOT found (it's at position 1250)
  4. Validation passes: "if new_name in names" is False
  5. Move operation proceeds
  6. Creates duplicate "duplicate" on server
  RESULT: DATA CORRUPTION
```

### Call Site 3C: loader.py:444-450

**Function Context**: `create_new_folder_on_rana()` - SAME VALIDATION BUG
```python
@pyqtSlot(dict, dict, str)
def create_new_folder_on_rana(self, project, selected_item, folder_name: str):
    """Create new folder on Rana and show warning when folder already exists"""
    root_path = selected_item["id"]
    names = [
        file["id"].strip("/")
        for file in get_tenant_project_files(  # <-- CALL
            self.communication,
            project["id"],
            params={"path": root_path} if root_path else None,
        )
        if file["type"] == "directory"
    ]
    if folder_name in names:  # <-- SAME VALIDATION BUG
        QMessageBox.warning(
            self.parent(), "Warning", f"Folder {folder_name} already exists."
        )
        return
    folder_path = root_path + folder_name + "/"
    success = create_folder(project["id"], params={"path": folder_path})
```

**SAME CRITICAL BUG**: Can create duplicate folder if target already exists beyond limit

**Impact**:
- File browser limited to 1000 items
- Duplicate detection validation broken
- **Can silently create duplicate files/folders**
- **DATA CORRUPTION POSSIBLE**

---

## FUNCTION 4: get_tenant_processes (Line 451)

### Function Definition
```python
def get_tenant_processes(communication: UICommunication):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/processes"
    params = {"limit": 100}  # <-- Hardcoded 100
    
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)
    
    if status:
        response = network_manager.content
        items = response["items"]  # <-- Only first 100
        return items
```

### Call Site 4A: api.py:721

**Function Context**: `get_process_id_for_tag()`
```python
def get_process_id_for_tag(communication: UICommunication, tag: str) -> Optional[str]:
    processes = get_tenant_processes(communication)  # <-- CALL
    for process in processes:
        if tag in process["tags"]:
            return process["id"]
```

**Called From**: Various job launching workflows

**Impact**:
- Only first 100 processes searchable
- If target process #150 doesn't exist in first 100
- `get_process_id_for_tag()` returns None
- **Job launch fails** or launches wrong process

**Real-World Scenario**:
```
User wants to launch process with tag "flood_simulation_v2"
Tenant has 150 processes
Process is at position 120 (beyond limit)
get_process_id_for_tag() searches only first 100
Returns None
Job launch fails with "Process not found" error
User frustrated, unaware process exists
```

**Git Context**: Commit 40781a1 reduced limit to 100 (was higher before)
- Suggests awareness of potential issues
- But wrong fix: reduced limit instead of adding pagination

---

## FUNCTION 5: get_project_jobs (Line 700)

### Function Definition
```python
def get_project_jobs(project_id: str):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    params = {"project_id": project_id, "limit": 100}  # <-- Hardcoded 100
    url = f"{api_url()}/tenants/{tenant}/jobs"
    network_manager = NetworkManager(url, authcfg_id)
    status, error = network_manager.fetch(params)
    
    if status:
        return network_manager.content  # <-- Returns entire response
    else:
        return None
```

### Call Site 5A: workers/persistent.py:100-125

**Function Context**: `JobMonitorWorker.run()`
```python
class JobMonitorWorker(QObject):
    jobs_added = pyqtSignal(list)
    job_updated = pyqtSignal(dict)
    
    def run(self):
        response = get_project_jobs(self.project_id)  # <-- CALL
        if not response:
            return
        current_jobs = response["items"]  # <-- Only first 100 jobs
        
        new_jobs = {
            job["id"]: job for job in current_jobs 
            if job["id"] not in self.active_jobs  # <-- Only 100 job IDs
        }
        self.jobs_added.emit(list(new_jobs.values()))
        self.active_jobs.update(new_jobs)  # <-- Tracking only first 100
        
        for job in current_jobs:  # <-- Iterates only first 100
            if job["id"] in new_jobs:
                # new job cannot be updated
                continue
            if (
                job["state"] != self.active_jobs[job["id"]]["state"]
                or job["process"] != self.active_jobs[job["id"]]["process"]
            ):
                self.job_updated.emit(job)  # <-- Never fires for jobs 101+
                self.active_jobs[job["id"]] = job
```

**Called From**: Persistent worker thread monitoring jobs

**CRITICAL BUG SCENARIO**:
```
Project has 150 active jobs

Iteration 1: fetch first 100 jobs
  - Jobs 1-100 added to active_jobs tracking
  - Jobs 101-150 IGNORED

Iteration 2 (5 minutes later): fetch first 100 jobs again
  - Job #150 completes on server
  - Job #150 NOT in current_jobs (only has 1-100)
  - job_updated signal NEVER fired
  - User never notified of completion
  - User waits indefinitely

RESULT: Job monitoring FAILS for jobs beyond limit
```

**Impact**:
- Job monitoring only tracks first 100 jobs
- State changes for jobs 101+ never detected
- UI never updated for jobs beyond limit
- **Users unaware of job completion/failure**
- **CRITICAL FOR PRODUCTION**: Jobs silently stop being monitored

---

## FUNCTION 6: get_schematisations (Line 589)

### Function Definition
```python
def get_schematisations(communication, icontains=""):
    authcfg_id = get_authcfg_id()
    tenant = get_tenant_id()
    url = f"{api_url()}/tenants/{tenant}/threedi-schematisations"
    network_manager = NetworkManager(url, authcfg_id)
    params = {"name__icontains": icontains, "limit": 100}  # <-- Hardcoded 100
    status, error = network_manager.fetch(params)
    
    if status:
        response = network_manager.content
        items = response["results"]  # <-- NOTE: uses "results" not "items"
        return items
    else:
        communication.show_error(f"Failed to retrieve schematisation: {error}")
        return []
```

**Special Note**: This is the ONLY function that uses `response["results"]` instead of `response["items"]`

### Call Site 6A: schematisation_browser.py:93

**Function Context**: Schematisation selection dialog
```python
def populate_table(self):
    self.table.clear()
    self.table.setHorizontalHeaderLabels(["Name", "Updated", "Created by"])
    self.table.setRowCount(0)
    self.ok_button.setEnabled(False)
    search_value = self.search_le.text()
    schematisations = get_schematisations(self.communication, search_value)  # <-- CALL
    for i, schematisation in enumerate(schematisations):  # <-- Iterates only first 100
        self.table.insertRow(self.table.rowCount())
        name_item = QTableWidgetItem(schematisation["name"])
        updated_item = QTableWidgetItem(
            format_activity_timestamp_str(schematisation["last_updated"])
        )
        creation_by_item = QTableWidgetItem(
            schematisation["created_by_first_name"]
            + " "
            + schematisation["created_by_last_name"]
        )
        name_item.setData(Qt.ItemDataRole.UserRole, schematisation)
        self.table.setItem(i, 0, name_item)
        self.table.setItem(i, 1, updated_item)
        self.table.setItem(i, 2, creation_by_item)
```

**Called From**: User opens schematisation browser dialog and searches

**Impact**:
- Search results limited to first 100 matches
- User searches for "model" and 200 match
- Only results 1-100 shown in dialog
- User searches for specific schematisation not in first 100
- **Result: "Not found" (but exists on server)**
- **User cannot select required 3Di model**
- **Blocks schematisation selection workflow**

**Real-World Scenario**:
```
User wants to use 3Di model "FloodRisk_Regional_v2024"
Tenant has 250 schematisations
Search for "FloodRisk" returns 150 matches
Dialog shows only matches 1-100
Desired model is match #120
User cannot find it
User gives up, cannot proceed with analysis
```

**Additional Issue: Field Name Inconsistency**
- All other functions use `response["items"]`
- **ONLY this uses `response["results"]`**
- Indicates different API endpoint/version
- Risk of copy-paste bugs during refactoring

---

## SUMMARY TABLE: ALL CALL SITES

| Function | Line | File | Usage | Impact |
|----------|------|------|-------|--------|
| get_user_tenants | 223 | rana_qgis_plugin.py | Multi-tenant menu | Breaks org selection |
| get_tenant_projects | 171 | projects_browser.py | UI display | Hides 1000+ projects |
| get_tenant_projects | 177-180 | projects_browser.py | Contributor list | Incomplete contributors |
| get_tenant_projects | 229 | projects_browser.py | Search/filter | False "not found" |
| get_tenant_project_files | 255 | files_browser.py | File display | Hides 1000+ files |
| get_tenant_project_files | 398-404 | loader.py | Duplicate detection | Allows duplicates |
| get_tenant_project_files | 444-450 | loader.py | Duplicate detection | Allows duplicates |
| get_tenant_processes | 721 | api.py | Process discovery | Process not found |
| get_project_jobs | 106 | workers/persistent.py | Job monitoring | Stops monitoring |
| get_schematisations | 93 | schematisation_browser.py | Search dialog | Results truncated |

---

## VALIDATION FAILURES

The most severe issues are **validation failures** where truncated data causes incorrect decisions:

### loader.py Lines 396-408: File Rename Validation
**Issue**: Checks for duplicate by searching incomplete file list
**Severity**: CRITICAL - Can create duplicate files
**Trigger**: Large directories (>1000 files)

### loader.py Lines 444-450: Folder Creation Validation
**Issue**: Same as above - checks incomplete list
**Severity**: CRITICAL - Can create duplicate folders
**Trigger**: Large directories (>1000 items)

These validation bugs are **NOT obvious** and will only manifest when:
1. Directory has >1000 items
2. Duplicate name exists beyond the 1000-item limit
3. User tries to create/rename to that name

This is **silent data corruption**.

