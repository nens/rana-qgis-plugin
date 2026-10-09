"""Context-menu actions for Rana file Browser items."""

from enum import Enum

from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QAction

import rana_qgis_plugin.icons as icons


class FileAction(Enum):
    OPEN_IN_QGIS = "Open"
    OPEN_WMS = "Open WMS in QGIS"
    OPEN_IN_BROWSER = "Open in Rana (web)"
    RENAME = "Rename"
    DELETE = "Delete"
    REFRESH = "Refresh"
    CREATE_DIRECTORY = "Create folder"
    UPLOAD_FILES = "Upload file(s)"
    VERSION_HISTORY = "Version history"
    VIEW_FILE_INFO = "View file info"

    @property
    def icon(self) -> QIcon:
        return _ICONS.get(self, QIcon())


_ICONS = {
    FileAction.OPEN_IN_QGIS: icons.download_icon,
    FileAction.OPEN_WMS: icons.wms_icon,
    FileAction.OPEN_IN_BROWSER: icons.link_icon,
    FileAction.RENAME: icons.edit_icon,
    FileAction.DELETE: icons.trash_icon,
    FileAction.REFRESH: icons.refresh_icon,
    FileAction.CREATE_DIRECTORY: icons.add_icon,
    FileAction.UPLOAD_FILES: icons.upload_icon,
    FileAction.VERSION_HISTORY: icons.history_icon,
}

_TOOLTIPS = {
    FileAction.OPEN_WMS: "Retrieve WMS URL and open layer in QGIS",
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
        actions = [FileAction.OPEN_IN_QGIS, FileAction.OPEN_WMS]
    else:
        actions = [FileAction.OPEN_IN_BROWSER] if data_type == "other" else []
    return (
        [FileAction.VIEW_FILE_INFO, FileAction.VERSION_HISTORY]
        + actions
        + [FileAction.RENAME, FileAction.DELETE]
    )


def get_folder_actions(is_root: bool = False) -> list[FileAction]:
    """Return the unconnected actions for a folder."""
    actions = [
        FileAction.OPEN_IN_QGIS,
        FileAction.REFRESH,
        FileAction.CREATE_DIRECTORY,
        FileAction.UPLOAD_FILES,
        FileAction.VERSION_HISTORY,
        FileAction.OPEN_IN_BROWSER,
    ]
    return actions if is_root else actions + [FileAction.RENAME, FileAction.DELETE]
