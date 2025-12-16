from enum import Enum
from typing import List, Optional

from qgis.PyQt.QtCore import QObject, pyqtSignal

from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils_api import get_tenant_file_descriptor


class FileAction(Enum):
    OPEN_IN_QGIS = "Open in QGIS"
    OPEN_WMS = "Open WMS in QGIS"
    SAVE_REVISION = "Save revision to Rana"
    SAVE_VECTOR_STYLING = "Save vector style to Rana"
    UPLOAD_FILE = "Save data to Rana"
    VIEW_REVISIONS = "View all revisions"
    DOWNLOAD_RESULTS = "Download results"
    RENAME = "Rename"
    DELETE = "Delete"

    def __lt__(self, other):
        # sort a list of file actions by order of definition here
        if self.__class__ is other.__class__:
            return self._member_names_.index(self.name) < self._member_names_.index(
                other.name
            )
        return NotImplemented


def get_file_actions_for_data_type(selected_item: dict) -> List[FileAction]:
    data_type = selected_item.get("data_type")
    actions = [FileAction.DELETE, FileAction.RENAME]
    # Add open in QGIS is supported for all supported data types
    if data_type in SUPPORTED_DATA_TYPES:
        actions.append(FileAction.OPEN_IN_QGIS)
    # Add save only for vector and raster files
    if data_type in ["vector", "raster"]:
        actions.append(FileAction.UPLOAD_FILE)
    # Add save vector style only for vector files
    if data_type == "vector":
        actions.append(FileAction.SAVE_VECTOR_STYLING)
    if data_type == "threedi_schematisation":
        actions += [FileAction.SAVE_REVISION, FileAction.VIEW_REVISIONS]
    # Add options to open WMS and download file and results only for 3Di scenarios
    if data_type == "scenario":
        descriptor = get_tenant_file_descriptor(selected_item["descriptor_id"])
        meta = descriptor["meta"] if descriptor else None
        if meta and meta["simulation"]["software"]["id"] == "3Di":
            actions += [FileAction.OPEN_WMS, FileAction.DOWNLOAD_RESULTS]
    return sorted(actions)


class FileActionSignals(QObject):
    file_deletion_requested = pyqtSignal(dict)
    file_rename_requested = pyqtSignal(dict, str)
    open_in_qgis_requested = pyqtSignal(dict)
    upload_file_requested = pyqtSignal(dict)
    save_vector_styling_requested = pyqtSignal(dict)
    save_revision_requested = pyqtSignal(dict)
    open_wms_requested = pyqtSignal(dict)
    download_file_requested = pyqtSignal(dict)
    download_results_requested = pyqtSignal(dict)
    view_all_revisions_requested = pyqtSignal(dict, dict)

    def get_signal(self, signal_type: FileAction) -> Optional[pyqtSignal]:
        signal_map = {
            FileAction.DELETE: self.file_deletion_requested,
            FileAction.RENAME: self.file_rename_requested,
            FileAction.OPEN_IN_QGIS: self.open_in_qgis_requested,
            FileAction.UPLOAD_FILE: self.upload_file_requested,
            FileAction.SAVE_VECTOR_STYLING: self.save_vector_styling_requested,
            FileAction.SAVE_REVISION: self.save_revision_requested,
            FileAction.OPEN_WMS: self.open_wms_requested,
            FileAction.DOWNLOAD_RESULTS: self.download_results_requested,
            FileAction.VIEW_REVISIONS: self.view_all_revisions_requested,
        }
        return signal_map.get(signal_type)
