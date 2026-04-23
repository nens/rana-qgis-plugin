# PAGINATION AUDIT REPORT: utils/api.py

## Executive Summary

**CRITICAL FINDINGS**: 6 out of 6 functions audited have **pagination handling issues**:
- **4 CRITICAL** functions silently truncate data without warning
- **2 HIGH** functions with limitations but less severe impact

All audit targets use hardcoded limits (100, 1000) without proper pagination logic.

---

## FUNCTION 1: get_user_tenants (Line 155)

### Implementation
```python
def get_user_tenants(communication: UICommunication, user_id: str):
    # ... network setup ...
    network_manager.fetch(params)
    items = response["items"]
    return items  # Returns raw items WITHOUT pagination
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Default API limit (not specified in function)
**RESPONSE**: Paginated endpoint with "items", "total", "offset", "limit"

### Call Sites
1. **rana_qgis_plugin.py:223**
   ```python
   self.tenants = get_user_tenants(self.communication, user_id)
   if len(self.tenants) > 1:
       switch_tenant_action = QAction(...)
   ```

### Data Flow Analysis
- **Usage**: Populates tenant selection menu
- **Critical Operation**: `if len(self.tenants) > 1` - checks if multiple tenants exist
- **Impact if Truncated**: 
  - If API default limit is 100 and user has >100 tenants → only first 100 shown
  - User cannot select organizations beyond the first page
  - **Severity**: CRITICAL - breaks multi-tenant functionality for large organizations

### Missing Data Validation
- No check for `response["total"]` vs `len(items)`
- No warning if data is truncated
- No fallback to paginate when needed

---

## FUNCTION 2: get_tenant_projects (Line 188)

### Implementation
```python
def get_tenant_projects(communication: UICommunication):
    params = {"limit": 1000}  # Hardcoded 1000
    network_manager.fetch(params)
    items = response["items"]
    return items  # Returns first 1000 only
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Hardcoded 1000 (offset defaults to 0)
**RESPONSE**: Paginated endpoint with "items", "total", "offset", "limit"

### Call Sites
1. **projects_browser.py:171**
   ```python
   self.tenant_projects = get_tenant_projects(self.communication)
   ```

2. **projects_browser.py:177-180** (update_users)
   ```python
   for project in self.tenant_projects
   for contributor in project["contributors"]
   # Builds complete list of all contributors across ALL projects
   ```

3. **projects_browser.py:229** (filter operations)
   ```python
   if text.lower() in project["name"].lower()
   # Filters from self.tenant_projects
   ```

### Data Flow Analysis
- **Critical Usage**: Full project enumeration required for:
  - Building contributor list (line 177-180)
  - Project filtering (lines 224-247)
  - Sorting and pagination UI (lines 249-268)

- **Impact if Truncated (>1000 projects)**:
  - Projects beyond 1000 hidden from user
  - Contributor list incomplete
  - Search results incomplete
  - Filtering excludes projects
  - **Users cannot see/access 1001+ projects**
  - **Severity**: CRITICAL - Data silently hidden

### Real-World Scenario
If tenant has 1500 projects:
- Only 1000 displayed
- 500 projects completely invisible
- If user searches for project #1250: "Not found" (but it exists on server)

---

## FUNCTION 3: get_tenant_project_files (Line 206)

### Implementation
```python
def get_tenant_project_files(communication, project_id: str, params: dict = None):
    # No default limit set - uses API default
    network_manager.fetch(params)
    items = response["items"]
    return items  # Returns first page only
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Caller-specified in params (e.g., limit=1000 from files_browser.py:252)
**RESPONSE**: Paginated endpoint with "items", "total"

### Call Sites
1. **files_browser.py:255** (fetch_and_populate)
   ```python
   params = {"limit": 1000}
   self.files = get_tenant_project_files(self.communication, project["id"], params)
   # Then iterates ALL files for UI population
   ```

2. **loader.py:398-404** (duplicate detection)
   ```python
   for file in get_tenant_project_files(..., params={"path": root_path}):
       if file["type"] == "directory":
           names = [file["id"].strip("/") for file in ...]
   if new_name in names:  # VALIDATION DEPENDS ON COMPLETE LIST
       QMessageBox.warning("Folder already exists")
   ```

3. **loader.py:444-450** (duplicate detection)
   ```python
   # Same pattern - checks if folder_name in names
   # If list is truncated, false positives possible
   ```

### Data Flow Analysis
- **Critical Validation**: Lines 396-408 in loader.py
  ```python
  names = [file["id"].strip("/") for file in get_tenant_project_files(...)]
  if new_name in names:
      return  # Skip move operation
  ```

- **Impact if Truncated (>1000 files)**:
  - File browser shows only first 1000 files
  - User cannot navigate beyond 1000 files
  - **Validation bug**: If folder #1250 exists but user tries to create "folder_x"
    - Function fetches only first 1000 files
    - Doesn't see existing "folder_x" at position 1250
    - **Allows duplicate folder creation**
  - Silent data loss in UI

- **Severity**: CRITICAL
  - Files hidden from user
  - Duplicate detection broken for large directories

### Real-World Scenario
Project has 1500 files. User wants to rename file #999 to "newname":
- Fetch gets first 1000 files (limit=1000)
- Checks if "newname" exists in first 1000
- File "newname" actually exists at position 1250 but is hidden
- **Allows move operation that creates duplicate**

---

## FUNCTION 4: get_tenant_processes (Line 451)

### Implementation
```python
def get_tenant_processes(communication: UICommunication):
    params = {"limit": 100}  # Hardcoded 100
    network_manager.fetch(params)
    items = response["items"]
    return items  # Returns first 100 only
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Hardcoded 100 (offset defaults to 0)
**RESPONSE**: Paginated endpoint with "items", "total"

### Call Sites
1. **api.py:721** (get_process_id_for_tag)
   ```python
   processes = get_tenant_processes(communication)
   for process in processes:
       if tag in process["tags"]:
           return process["id"]
   return None
   ```

2. **workers/persistent.py:106**
   ```python
   response = get_project_jobs(...)  # Different function, but similar pattern
   current_jobs = response["items"]
   ```

### Data Flow Analysis
- **Process Discovery**: Used to find process by tag
- **Impact if Truncated (>100 processes)**:
  - Only first 100 processes available for job launches
  - Processes 101+ cannot be discovered by tag
  - **Jobs launched with wrong process** or process not found
  - Severity**: CRITICAL - breaks process execution for users with many processes

### Git History
Commit 40781a1: "Reduce limit for get_tenant_processes to 100"
- Was apparently higher before, reduced to 100
- **No pagination added** - just reduced the limit
- Indicates awareness of potential overflow but wrong solution

---

## FUNCTION 5: get_project_jobs (Line 700)

### Implementation
```python
def get_project_jobs(project_id: str):
    params = {"project_id": project_id, "limit": 100}
    network_manager.fetch(params)
    return network_manager.content  # Returns entire response with items
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Hardcoded 100
**RESPONSE**: Paginated endpoint with "items", "total", "offset", "limit"

### Call Sites
1. **workers/persistent.py:106-125** (job monitoring loop)
   ```python
   response = get_project_jobs(self.project_id)
   current_jobs = response["items"]
   
   new_jobs = {job["id"]: job for job in current_jobs if ...}
   self.jobs_added.emit(list(new_jobs.values()))
   
   self.active_jobs.update(new_jobs)
   
   for job in current_jobs:
       if job["id"] in self.active_jobs:
           if job["state"] != self.active_jobs[job["id"]]["state"]:
               self.job_updated.emit(job)
   ```

### Data Flow Analysis
- **Critical Function**: Job monitoring/tracking
- **Cache Comparison**: Active jobs compared against current_jobs
- **Impact if Truncated (>100 jobs)**:
  - Jobs beyond position 100 never added to active_jobs tracking
  - Job state updates for jobs 101+ never detected
  - **Jobs silently stop being monitored**
  - No UI update for jobs beyond limit
  - User unaware of job 150's completion/failure
  - **Severity**: CRITICAL - Job monitoring failures in production

### Real-World Scenario
Project has 150 active jobs:
- Monitoring fetches first 100
- Job #125 completes on server
- job_updated signal never fired (job not in active_jobs)
- User waits indefinitely, unaware of completion

---

## FUNCTION 6: get_schematisations (Line 589)

### Implementation
```python
def get_schematisations(communication, icontains=""):
    params = {"name__icontains": icontains, "limit": 100}
    network_manager.fetch(params)
    items = response["results"]  # NOTE: uses "results" not "items"
    return items
```

### Pagination Status
**USES**: `simple_fetch()` with NO pagination
**LIMIT**: Hardcoded 100
**RESPONSE**: Endpoint returns "results" (not "items") with pagination
**NOTE**: **INCONSISTENT FIELD NAME** - uses "results" instead of "items"

### Call Sites
1. **schematisation_browser.py:93-109** (search/selection dialog)
   ```python
   schematisations = get_schematisations(self.communication, search_value)
   for i, schematisation in enumerate(schematisations):
       self.table.insertRow(...)
       name_item = QTableWidgetItem(schematisation["name"])
       # Populates table with available schematisations
   ```

### Data Flow Analysis
- **Usage**: Search dialog to select schematisation for 3Di model
- **Search Semantics**: `icontains` parameter suggests partial string matching
- **Impact if Truncated (>100 matches)**:
  - Search results limited to first 100 matching schematisations
  - User cannot access schematisations beyond results #100
  - If user searches for "model" and 200 match:
    - **Only first 100 shown in dialog**
    - Desired schematisation at position #150 invisible
  - **User cannot select required 3Di model**
  - Severity**: CRITICAL - Blocks schematisation selection workflow

### Additional Issue: Field Name Inconsistency
- All other functions use `response["items"]`
- **ONLY this function uses `response["results"]`**
- Suggests different API version or endpoint
- Risk of copy-paste bugs if code refactored

---

## COMPARISON: Functions CORRECTLY Using paginated_fetch()

For reference, these functions properly handle pagination:

### get_project_publications (Line 713)
```python
def get_project_publications(project_id: str):
    params = {"project_id": project_id}
    return paginated_fetch(url, 100, params)  # CORRECT: uses paginated_fetch
```

### get_publication_version_files (Line 776)
```python
def get_publication_version_files(publication_id: str, version: int) -> list:
    return paginated_fetch(url, 100)  # CORRECT: uses paginated_fetch
```

These functions properly iterate through ALL pages and return complete result sets.

---

## ROOT CAUSE ANALYSIS

### Why Were 6 Functions Missed?

1. **Inconsistent Pattern**: `paginated_fetch()` was added in commit 11acbfc (Feb 23, 2026)
   - Some functions updated
   - **Others left behind without pagination**

2. **Hardcoded Limits Don't Hide the Problem**:
   ```python
   params = {"limit": 1000}  # Looks safe
   ```
   But still only fetches first page if total > 1000

3. **No Validation of Total**:
   - Response contains `response["total"]` field
   - No function checks if `len(items) < total`
   - Silent truncation possible

4. **Different Endpoint Response Formats**:
   - Some use "items", one uses "results"
   - Makes systematic migration to paginated_fetch() harder

---

## SEVERITY ASSESSMENT

| Function | Limit | Impact | Severity |
|----------|-------|--------|----------|
| get_user_tenants | Unknown default | Breaks multi-tenant menu | CRITICAL |
| get_tenant_projects | 1000 | Hides 1000+ projects completely | CRITICAL |
| get_tenant_project_files | 1000 | Hides files, breaks validation | CRITICAL |
| get_tenant_processes | 100 | Process discovery fails | CRITICAL |
| get_project_jobs | 100 | Job monitoring stops | CRITICAL |
| get_schematisations | 100 | Search results truncated, blocking workflow | CRITICAL |

**All 6 functions are CRITICAL for production use**

---

## ACTUAL IMPACT vs "limit=100" Defense

The audit counters the common misconception: "It only fetches 100 items, so users won't notice."

**Counter-evidence**:
1. **get_tenant_projects uses limit=1000** - Still truncates at 1000
2. **Validation logic depends on complete data** - loader.py duplicate checks fail silently
3. **UI becomes incomplete** - Users search/filter incomplete data set
4. **Job monitoring breaks** - No warning, silent failure
5. **Process discovery fails** - Wrong process executed or error thrown
6. **Search results truncated** - User cannot find required schematisation

The limit values chosen create a **false sense of security** while data silently gets lost.

---

## RECOMMENDATIONS

1. **Immediate**: Replace all 6 functions to use `paginated_fetch()`
2. **Add validation**: Check if `len(items) < response["total"]` and warn
3. **Unit tests**: Add tests with mock responses having total > limit
4. **Consistency**: Use "items" field name across all endpoints (or handle "results")
5. **Monitoring**: Add telemetry to detect truncation in production

