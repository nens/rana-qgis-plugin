## Authentication

The Rana Desktop Client (RDC) connects to the Rana backend via the API
using OAuth2 authentication workflow. The OAuth2 authentication is configured
via the `setup_oauth2` method in `rana_qgis_plugin/auth.py`.

Once you logged in to Rana, it also attempts to configure authentication for
3Di using a 3Di personal API key. Your 3Di personal API key is generated
automatically via the Rana API in case there is none yet. The 3Di authentication
is configured via the `setup_3di_auth` method in `rana_qgis_plugin/auth_3di.py`.


## Related 3Di plugins

The RDC also contains the following 3Di plugins:

- [3Di Models & Simulations](https://github.com/nens/threedi-api-qgis-client)
- [3Di Results Analysis](https://github.com/nens/threedi-results-analysis)
- [3Di Schematisation Editor](https://github.com/nens/threedi-schematisation-editor)

However, the only real interaction between RDC and 3Di plugin is to load a
schematisation via the 3Di Models & Simulations plugin as in
[here](https://github.com/nens/rana-qgis-plugin/blob/main/rana_qgis_plugin/utils.py#L91).


## Rana styling for QGIS

Some basic Rana stylings (e.g. colors, icons) are added to the RDC via the below plugin:

- [Rana QGIS Customisations](https://github.com/nens/rana-qgis-customisations)


## How to make requests in RDC

Currently, there are 2 ways to make requests in RDC:

- Using the `requests` library for requests that do not require authentication
- Using the `Qt Network` library for requests to Rana that require OAuth2 authentication

The `NetworkManager` class uses the Qt Network library to add OAuth2 token to
the requests to Rana. The `NetworkManager` class can be found in
`rana_qgis_plugin/network_manager.py`.


## Workers

Some tasks that are time consuming are done in separate workers, including:

- File download in the `FileDownloadWorker`
- File upload in the `FileUploadWorker`

The workers are defined in `rana_qgis_plugin/workers.py`.


## QGIS / Rana Vector style

Vector styles are stored in QGIS as `*.qml` files. We use a library to convert
these QGIS styles to Maplibre styles for the Rana Web client that is called
[GeoCat/bridge-style](https://github.com/GeoCat/bridge-style). The source code
of this library is copied to `rana_qgis_plugin/libs/bridgestyle` for use in the
RDC.


## Isort & Black

This repo uses `isort` and `black` for imports and code format. Run the following
commands to format the code:

- `isort rana_qgis_plugin`
- `black -l 120 rana_qgis_plugin`

Note, the `libs/bridgestyle` is currently not formatted.


## Deployment of the Rana plugin

Deployment is done similar to other 3Di plugins. Please refer to the **README**
for more information.

The plugin can be downloaded at: https://plugins.lizard.net/


## Installer for the RDC as a standalone desktop application

The installer for the RDC is in the [3Di Modeller Interface](https://github.com/nens/threedi-modeller-interface-installer).

Currently, it is in a separate branch called [rana-desktop-client](https://github.com/nens/threedi-modeller-interface-installer/tree/rana-desktop-client).

Please refer to the above repo for how to deploy the installer to production.
The installer can be downloaded at: https://docs.3di.live/modeller-interface-downloads/.


## Switching to test environment

Currently, you can swith the RDC to talk to the Rana test API by modifying the
following constants in `rana_qgis_plugin/constant.py`:

- `COGNITO_CLIENT_ID = "77chge3p2dq74a5uspvt136piu"`
- `BASE_URL = "https://test.ranawaterintelligence.com"`
