from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Optional, cast

if TYPE_CHECKING:
    from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef


@dataclass(frozen=True)
class UploadableLayerItem:
    """A linked Rana file and its local source path."""

    rana_ref: "RanaLayerRef"
    local_file_path: Path
    layer_name: str
    project_name: str


class DataType(Enum):
    raster = "raster"
    vector = "vector"
    schematisation = "threedi-schematisation"
    scenario = "scenario"

    @classmethod
    def from_value(cls, value: str) -> Optional["DataType"]:
        if value in cls._value2member_map_:
            return cast("DataType", cls._value2member_map_[value])
        return None


@dataclass(frozen=True)
class StyleUploadItem:
    """Inputs for one style upload operation."""

    data_type: DataType
    local_file_path: str
    file_ref_str: str
    upload_func: Callable[[list], object]
    layer_in_file: str | None = None
    project_id: str | None = None
    descriptor_id: str | None = None


@dataclass
class RanaFileData:
    file: dict
    data_type: DataType


@dataclass(kw_only=True)
class RanaPublicationFileData(RanaFileData):
    file_tree: list[str]
    display_name: str  # name for layer in Qgis layer panel
    style_id: Optional[str] = None
    layer_in_file: Optional[str] = None


@dataclass
class LocalPublicationFileData(RanaPublicationFileData):
    local_path: str

    @staticmethod
    def from_file_data(
        local_path: str, file_data: RanaPublicationFileData
    ) -> "LocalPublicationFileData":
        return LocalPublicationFileData(local_path=local_path, **file_data.__dict__)


@dataclass(frozen=True)
class OpenFileRequest:
    """Request to open all layers from a Rana file."""

    project: dict
    file_item: dict


@dataclass(frozen=True)
class OpenLayerRequest:
    """Request to open a single layer from a Rana vector file."""

    project: dict
    file_item: dict
    layer_name: str
    layer_id: str | None = None


@dataclass(frozen=True)
class OpenFolderRequest:
    """Request to open all openable files under a Rana folder."""

    project: dict
    folder_path: str
