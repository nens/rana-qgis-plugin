from enum import Enum
from typing import List, Optional

from qgis.PyQt.QtCore import QObject, pyqtSignal
from qgis.PyQt.QtWidgets import QApplication

from rana_qgis_plugin.auth_3di import has_3di_authcfg
from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils.api import FileDescriptorStatus, get_tenant_file_descriptor


class FileAction(Enum):
    # Actions related to accessing data
    OPEN_IN_QGIS = "Open in QGIS"
    OPEN_WMS = "Open WMS in QGIS"
    DOWNLOAD_RESULTS = "Download Results"
    OPEN_IN_FILE_BROWSER = "Open in file browser"
    OPEN_IN_BROWSER = "Open in browser"
    COPY_WMS_URL = "Copy WMS URL"
    # Actions related to viewing or modifying files on Rana
    SAVE_REVISION = "Upload to Rana"
    SAVE_STYLING = "Save style to Rana"
    UPLOAD_FILE = "Save Data to Rana"
    EXPORT_GPKG = "Export to GeoPackage"
    VIEW_REVISIONS = "View all Revisions"
    HISTORY = "History"
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
            actions.append(FileAction.COPY_WMS_URL)
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
