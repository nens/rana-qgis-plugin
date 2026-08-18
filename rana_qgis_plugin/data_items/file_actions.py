"""Context-menu actions for Rana file Browser items."""

from enum import Enum

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

from rana_qgis_plugin.icons import (
    add_icon,
    download_icon,
    edit_icon,
    history_icon,
    link_icon,
    trash_icon,
    upload_icon,
    wms_icon,
)


class FileAction(Enum):
    OPEN_IN_QGIS = "Open in QGIS"
    OPEN_WMS = "Open WMS in QGIS"
    DOWNLOAD_RESULTS = "Download results"
    OPEN_IN_BROWSER = "Open in web viewer"
    RENAME = "Rename"
    DELETE = "Delete"
    REFRESH = "Refresh"
    CREATE_DIRECTORY = "Create directory"
    UPLOAD_FILES = "Upload file(s)"
    VERSION_HISTORY = "Version history"
    VIEW_FILE_INFO = "View file info"

    @property
    def icon(self) -> QIcon:
        return _ICONS.get(self, QIcon())


_ICONS = {
    FileAction.OPEN_IN_QGIS: download_icon,
    FileAction.OPEN_WMS: wms_icon,
    FileAction.DOWNLOAD_RESULTS: download_icon,
    FileAction.OPEN_IN_BROWSER: link_icon,
    FileAction.RENAME: edit_icon,
    FileAction.DELETE: trash_icon,
    FileAction.REFRESH: link_icon,
    FileAction.CREATE_DIRECTORY: add_icon,
    FileAction.UPLOAD_FILES: upload_icon,
    FileAction.VERSION_HISTORY: history_icon,
}

_TOOLTIPS = {
    FileAction.OPEN_WMS: "Retrieve WMS URL and open layer in QGIS",
    FileAction.DOWNLOAD_RESULTS: "Download results and open in Rana Results Analysis",
    FileAction.OPEN_IN_BROWSER: "Open file in Rana web viewer",
    FileAction.CREATE_DIRECTORY: "Create a new folder",
    FileAction.UPLOAD_FILES: "Upload files to this location",
    FileAction.VERSION_HISTORY: "View file version history",
    FileAction.VIEW_FILE_INFO: "View file metadata",
}


def get_action_tooltip(action: FileAction) -> str:
    """Return the tooltip for an action, or an empty string."""
    return _TOOLTIPS.get(action, "")


def create_separator(parent) -> QAction:
    """Create a separator action for a QGIS Browser context menu."""
    separator = QAction(parent)
    separator.setSeparator(True)
    return separator


def get_file_actions(data_type: str) -> list[FileAction]:
    """Return the unconnected actions for a file data type."""
    if data_type in {"vector", "raster", "threedi_schematisation"}:
        actions = [FileAction.OPEN_IN_QGIS, FileAction.OPEN_IN_BROWSER]
    elif data_type == "scenario":
        # Keep these as static placeholders for now. Descriptor-dependent
        # availability is checked later, when the actions are connected.
        actions = [FileAction.OPEN_WMS, FileAction.DOWNLOAD_RESULTS]
    else:
        actions = [FileAction.OPEN_IN_BROWSER] if data_type == "other" else []
    return (
        [FileAction.VIEW_FILE_INFO] + actions + [FileAction.RENAME, FileAction.DELETE]
    )


def get_folder_actions(is_root: bool = False) -> list[FileAction]:
    """Return the unconnected actions for a folder."""
    actions = [
        FileAction.REFRESH,
        FileAction.CREATE_DIRECTORY,
        FileAction.UPLOAD_FILES,
        FileAction.VERSION_HISTORY,
        FileAction.OPEN_IN_BROWSER,
    ]
    return actions if is_root else actions + [FileAction.RENAME, FileAction.DELETE]
