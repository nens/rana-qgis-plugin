## Tested paths

### Plugin basics

* Smoke test: assert plugin is loaded and data provider is listed
* Login / logout with stored credentials
  * test preset auth result in logged in plugin
  * logout via context menu and verify "Login" is visible
  * verify authcfg is removed after logout
* Refresh on refocus:
  * assert that refocus from outside qgis triggers refresh
  * assert that refocus from within qgis does not trigger refresh
* Select projects
  * test if hide via context menu hides project
  * test if hide via context menu results in uncheck project in project selector
  * test if changing selected projects via project selector updates project list


### Datasoure

* Test if project is visible after adding and refresh
* Test if project is no longer visible after removing and refresh
* Test if expected folder tree is shown in Files item