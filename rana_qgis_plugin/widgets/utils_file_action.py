from enum import Enum
from typing import List, Optional

from qgis.PyQt.QtCore import QObject, QUrl, pyqtSignal
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QApplication

from rana_qgis_plugin.auth_3di import has_3di_authcfg
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.icons import (
    copy_icon,
    dir_icon,
    download_icon,
    edit_icon,
    history_icon,
    link_icon,
    style_icon,
    trash_icon,
    upload_icon,
    wms_icon,
)
from rana_qgis_plugin.utils.api import (
    FileDescriptorStatus,
    get_tenant_file_descriptor,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils.settings import base_url, get_tenant_id


class FileAction(Enum):
    # Actions related to accessing data
    OPEN_IN_QGIS = "Open"
    OPEN_WMS = "Open WMS in QGIS"
    DOWNLOAD_RESULTS = "Download"
    OPEN_IN_FILE_BROWSER = "Open in local folder"
    OPEN_IN_BROWSER = "Open in web viewer"
    # Actions related to viewing or modifying files on Rana
    SAVE_REVISION = "Save new revision"
    SAVE_STYLING = "Save style"
    UPLOAD_FILE = "Save data"
    EXPORT_GPKG = "Export to gpkg"
    VIEW_REVISIONS = "View all revisions"
    HISTORY = "File History"
    RENAME = "Rename"
    DELETE = "Delete"
    REMOVE_FROM_PROJECT = "Remove from Project"

    def __lt__(self, other):
        # sort a list of file actions by order of definition here
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) < self._member_names_.index(
                other.name
            )
        return NotImplemented

    def get_tooltip(self, data_type: str = None) -> str:
        """Return the tooltip for this action.

        Args:
            data_type: The file's data type, used for context-dependent tooltips.
        """
        if self == FileAction.OPEN_IN_QGIS:
            if data_type == "threedi_schematisation":
                return "Download schematisation and open in Schematisation Editor"
            return f"Download {data_type} file and open in QGIS"
        if self == FileAction.OPEN_IN_FILE_BROWSER:
            if data_type == "scenario":
                return "Open results folder in file browser"
            elif data_type == "threedi_schematisation":
                return "Open revision folder in file browser"
            return "Open folder containing this file"
        return _TOOLTIPS.get(self, "")

    @property
    def icon(self) -> QIcon:
        """Return the QIcon for this action."""
        return _ICONS.get(self, QIcon())


_TOOLTIPS = {
    FileAction.DOWNLOAD_RESULTS: ("Download results and open in Rana Results Analysis"),
    FileAction.SAVE_REVISION: (
        "Save your local changes as a new revision to this schematisation"
    ),
    FileAction.SAVE_STYLING: "Save your local style to Rana web Platform",
    FileAction.UPLOAD_FILE: ("Save your local data changes to Rana web Platform"),
    FileAction.EXPORT_GPKG: "Export to GeoPackage for use in publication",
    FileAction.VIEW_REVISIONS: (
        "View all revisions that are part of this schematisation"
    ),
    FileAction.HISTORY: "View file history",
    FileAction.OPEN_IN_BROWSER: "Open schematisation in Rana HCC",
    FileAction.OPEN_WMS: "Retrieve WMS url and open layer in QGIS",
}

_ICONS = {
    FileAction.OPEN_IN_QGIS: download_icon,
    FileAction.OPEN_WMS: wms_icon,
    FileAction.DOWNLOAD_RESULTS: download_icon,
    FileAction.OPEN_IN_FILE_BROWSER: dir_icon,
    FileAction.OPEN_IN_BROWSER: link_icon,
    FileAction.SAVE_REVISION: upload_icon,
    FileAction.SAVE_STYLING: style_icon,
    FileAction.UPLOAD_FILE: upload_icon,
    FileAction.EXPORT_GPKG: copy_icon,
    FileAction.VIEW_REVISIONS: history_icon,
    FileAction.HISTORY: history_icon,
    FileAction.RENAME: edit_icon,
    FileAction.DELETE: trash_icon,
    FileAction.REMOVE_FROM_PROJECT: trash_icon,
    FileAction.OPEN_WMS: wms_icon,
}


def get_file_actions(selected_item: dict, descriptor: dict = None) -> List[FileAction]:
    data_type = selected_item.get("data_type")
    actions = get_file_actions_by_data_type(data_type)
    if data_type == "scenario":
        if descriptor is None:
            descriptor = get_tenant_file_descriptor(selected_item["descriptor_id"])
        actions = get_scenario_actions(actions, descriptor)
    # Add options to open WMS and download file and results only for 3Di scenarios
    return sorted(actions)


def get_file_actions_by_data_type(data_type: str) -> List[FileAction]:
    actions = [FileAction.DELETE, FileAction.RENAME]
    # Add open in QGIS is supported for all supported data types
    if data_type in SUPPORTED_DATA_TYPES:
        if (data_type != "threedi_schematisation") or has_3di_authcfg():
            actions.append(FileAction.OPEN_IN_QGIS)
            # Add open in file browser to any file type that can be opened
            # Actual check for file availibility will be done downstream
            actions.append(FileAction.OPEN_IN_FILE_BROWSER)
    # Add save only for vector and raster files
    if data_type in ["vector", "raster"]:
        actions.append(FileAction.UPLOAD_FILE)
        actions.append(FileAction.SAVE_STYLING)
        actions.append(FileAction.OPEN_IN_BROWSER)
    elif data_type == "threedi_schematisation":
        # Schematisation are not deleted, therefore replace DELETE with REMOVE_FROM_PROJECT
        actions = [FileAction.REMOVE_FROM_PROJECT] + actions[1:]
        if has_3di_authcfg():
            actions += [FileAction.SAVE_REVISION, FileAction.VIEW_REVISIONS]
        actions += [FileAction.EXPORT_GPKG, FileAction.OPEN_IN_BROWSER]
    return sorted(actions)


def get_scenario_actions(
    actions: list[FileAction], descriptor: dict
) -> List[FileAction]:
    meta = descriptor["meta"] if descriptor else None
    if meta and "id" in meta:
        actions.append(FileAction.DOWNLOAD_RESULTS)
        if meta["simulation"]["software"]["id"] == "3Di":
            actions.append(FileAction.OPEN_WMS)
        # Add open in file browser to any file type that can be opened
        # Actual check for file availibility will be done downstream
        actions.append(FileAction.OPEN_IN_FILE_BROWSER)
    # remove any interactions for objects that are being processed
    elif (
        FileDescriptorStatus.from_fd_response(descriptor)
        == FileDescriptorStatus.processing
    ):
        return []
    return actions


def copy_wms_url_to_clipboard(file: dict, communication=None):
    """Copy the WMS URL of a file to the clipboard.

    Args:
        file: The file dict containing a descriptor_id.
        communication: Optional UICommunication instance for user feedback.
    """
    descriptor = get_tenant_file_descriptor(file["descriptor_id"])
    wms_link = next(
        (link for link in descriptor["links"] if link["rel"] == "wms"), None
    )
    communication.log_info(f"WMS URL: {wms_link['href']}")
    if wms_link:
        QApplication.clipboard().setText(wms_link["href"])
        if communication:
            communication.bar_info("WMS URL copied to clipboard.")
    elif communication:
        communication.show_warn("No WMS URL available for this file.")


def retrieve_url(selected_item: dict, project: dict, communication) -> QUrl:
    if selected_item.get("data_type") == "threedi_schematisation":
        schematisation = get_threedi_schematisation(
            communication, selected_item["descriptor_id"]
        )
        if not schematisation or not schematisation.get("management_url"):
            return None
        return QUrl(schematisation["management_url"])
    elif selected_item.get("data_type") in ["vector", "raster"]:
        link = f"{base_url()}/{get_tenant_id()}/projects/{project['slug']}?tab=1&"
        file_id = selected_item.get("id")
        if "/" in file_id:
            path = file_id.rsplit("/", 1)[0]
            fileName = file_id.rsplit("/", 1)[1]
            link = link + f"path={path.replace('/', ',')}&fileName={fileName}"
        else:
            link = link + f"fileName={file_id}"
    return QUrl(link)


class FileActionSignals(QObject):
    file_deletion_requested = pyqtSignal(dict)
    file_rename_requested = pyqtSignal(dict, str)
    open_in_qgis_requested = pyqtSignal(dict)
    upload_file_requested = pyqtSignal(dict)
    save_styling_requested = pyqtSignal(dict)
    save_revision_requested = pyqtSignal(dict)
    open_wms_requested = pyqtSignal(dict)
    export_gpkg_requested = pyqtSignal(dict)
    download_file_requested = pyqtSignal(dict)
    download_results_requested = pyqtSignal(dict)
    view_all_revisions_requested = pyqtSignal(dict, dict)

    def get_signal(self, signal_type: FileAction) -> Optional[pyqtSignal]:
        signal_map = {
            FileAction.DELETE: self.file_deletion_requested,
            FileAction.REMOVE_FROM_PROJECT: self.file_deletion_requested,
            FileAction.RENAME: self.file_rename_requested,
            FileAction.OPEN_IN_QGIS: self.open_in_qgis_requested,
            FileAction.UPLOAD_FILE: self.upload_file_requested,
            FileAction.SAVE_STYLING: self.save_styling_requested,
            FileAction.SAVE_REVISION: self.save_revision_requested,
            FileAction.OPEN_WMS: self.open_wms_requested,
            FileAction.EXPORT_GPKG: self.export_gpkg_requested,
            FileAction.DOWNLOAD_RESULTS: self.download_results_requested,
            FileAction.VIEW_REVISIONS: self.view_all_revisions_requested,
            FileAction.HISTORY: self.view_all_revisions_requested,
        }
        return signal_map.get(signal_type)
