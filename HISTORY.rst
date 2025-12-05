History
=======

1.1.21 (unreleased)
-------------------

- Add revision view and new simulation button
- Replace file interaction buttons with context menu
- Download generated postprocessing rasters.
- Replace page specific refresh buttons with single refresh button
- Refresh files browser, file view and revisions view every 60 seconds


1.1.20 (2025-11-18)
-------------------

- Bump dependency loader to 1.2.6.


1.1.19 (2025-11-18)
-------------------

- Bump dependency loader to 1.2.5.


1.1.18 (2025-10-01)
-------------------

- Added and removed workaround for proper sprite naming (until this is fixed in frontend (nens/rana#2621))
- Remove duplicates from bridgestyle warnings about non-supported styling options (#93)
- Preparation for Qt/QGIS4.0
- New bridgestyle version: added support for conversion of fill line patterns (#2324)
- New bridgestyle version: added support for conversion of Else filter (#2326)
- New bridgestyle version: Added support for conversion of IF (NOT) TRUE in styling filter (#2326)


1.1.17 (2025-09-08)
-------------------

- Bumped dependency loader.


1.1.16 (2025-09-01)
-------------------

- Workaround for proper conversion of text-halo-width and newlines (until this is fixed in bridge-style) (nens/rana#2323)
- Rana plugin hangs when aborting an upload (#89)


1.1.15 (2025-08-28)
-------------------

- Prevent N&S Dependency Loader from getting disabled (nens/nens-dependency-loader#19)


1.1.14 (2025-07-31)
-------------------

- Fix loading of layers in QGIS.


1.1.13 (2025-07-23)
-------------------

- Fix broken layout in settings dialog.


1.1.12 (2025-07-18)
-------------------

- Fetch file download url and descriptor from dedicated endpoints instead of File object (#53)
- Added UML diagram (#72)
- Separate browsing (RanaBrowser) and loading (Loader) (#70)


1.1.11 (2025-07-16)
-------------------

Bump Dependency Loader plugin version to 1.2.1 (nens/nens-dependency-loader#14)


1.1.10 (2025-07-15)
-------------------

- Next to SSO login, allow username-password option (#82)


1.1.9 (2025-07-08)
------------------

- Added "Add File to Rana" button (nens/rana#1951)
- Upload new file: set last used directory in settings (nens/rana#2058)
- Reload local file url and other metadata after uploading to Rana.
- Show "Latest revision number" field in 3Di schematisation file details. (nens/rana#1874)
- Show description field.
- Add option to pass Rana URL to QGIS. (nens/rana-qgis-plugin#61)
- Add option to load WMS layers of 3Di scenarios (nens/rana-qgis-plugin#51)
- Add option to download scenario zip (nens/rana-qgis-plugin#51)
- Reload file ui after uploading file. (nens/rana#41)
- Add refresh button to project and file overview to allow manual reloading.
- Add option to download individual scenario results and store in 3Di working directory (#51)
- Add feature that downloaded scenario result can be loaded in 3Di Results Analysis Tool (#51)
- Remove GeoCat/bridgestyle from the plugin since it is now on PyPI. (nens/rana-qgis-plugin#71)
- Fix update_breadcrumbs; refresh file details after loading file from Rana. (nens/rana-qgis-plugin#80)


1.1.8 (2025-06-16)
------------------

- Adapt file details retrieval due to backend change. nens/rana#1691
- Added progress bar when downloading schematisation via M&S plugin. nens/rana#1745
- Added Settings menu to configure authentication. nens/rana#1252


1.1.7 (2025-06-10)
------------------

- Fixed symbol compatibility test and warning in bridge-style code. #1681
- Desktop client crashes when opening a vector file that isn't "Complete" in processing. #1731
- Only retrieve vector style file for vector files. nens/rana#1541
- Add lint workflow with pre-commit and ruff. nens/rana#1795
- Run linter.
- Add build and release workflow. nens/rana#1794
- Use dict to show user-friendly data type name. nens/rana#1872
- Split Rana save button into style save and data save button. nens/rana#1840


1.1.6 (2025-04-15)
------------------

- Show warning messages when converting vector files fails
- Logging out does not open web browser anymore


1.1.5 (2025-04-14)
------------------

- Add bridgestyle package to libs: #24
- Save and sync vector styling files to Rana: #25
- Fix wrong key name in sprites.json in bridgestyle: #27
- Fix local_dir_structure name to exclude file extension
- Make table cells not editable in the file details table
- Add technical documentation for Rana Desktop Client
- Sort projects by last activity in ascending order
- Include the vector style upload in the file upload process: #28
- Fix simple markers not showing in the Web Client: #29


1.1.4 (2025-02-28)
------------------

- Fix QGIS crash caused by add_rana_menu method: #23
- Revert PR #22 to fix QGIS crash.


1.1.3 (2025-02-25)
------------------

- Fix QGIS crash due to https://github.com/nens/rana/issues/1390: #22


1.1.2 (2025-02-18)
------------------

- Fix vector file with multiple layers cannot be opened in QGIS: #21


1.1.1 (2025-01-23)
------------------

- Use project slug instead of project name for local directory name.


1.1.0 (2025-01-17)
------------------

- Fix bug getting 3Di personal API key failed.


1.0.0 (2025-01-14)
------------------

- Change cognito client ID and base URL to production: #20


0.1.14 (2024-12-23)
------------------

- Hide vertical header in the File table widget.
- Show progress bar when navigating using the breadcrumbs.
- Set and select a tenant: #19
- Show scenario details: #19


0.1.13 (2024-12-17)
------------------

- Fix datetime ISO format bug with python 3.9.


0.1.12 (2024-12-16)
------------------

- Fix datetime ISO format bug with python 3.9.


0.1.11 (2024-12-16)
------------------

- Apply sorting to all projects, not only paginated ones: #17
- Show progress bar and use workers for long running tasks: #18


0.1.10 (2024-12-09)
------------------

- Change 3Di personal API keys endpoint (backend change).


0.1.9 (2024-12-03)
------------------

- Fix sorting on last modified for files


0.1.8 (2024-12-03)
------------------

- Sorting for all columns: #16
- Login to 3Di from Rana using a personal API key: #15


0.1.7 (2024-11-29)
------------------

- Fix f-string syntax error: #14


0.1.6 (2024-11-29)
------------------

- Login/logout actions and rana menu: #13
- About Rana dialog: #13
- Improvements for Rana QGIS plugin: #12
- Persist authentication token between QGIS sessions
- Use QGIS 3.40 in Dockerfile


0.1.5 (2024-11-12)
------------------

- Show and open 3Di schematisation: #9


0.1.4 (2024-10-14)
------------------

- Fix bug with file conflict check: #8
- Dock the plugin to the right side panel, add pagination, search bar for projects: #10
- Add UI communication system: #11


0.1.1 (2024-10-08)
------------------

- Add Rana icon to the plugin: #7


0.1.0 (2024-10-07)
------------------

- First release.
