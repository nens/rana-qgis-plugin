from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DataType(Enum):
    raster = "raster"
    vector = "vector"


@dataclass
class RanaFileData:
    file: dict
    data_type: DataType


@dataclass(kw_only=True)
class RanaPublicationFileData(RanaFileData):
    file_tree: list[str]
    display_name: str  # name for layer in Qgis layer panel
    style_id: Optional[str] = None


@dataclass
class RanaRasterPublicationFileData(RanaPublicationFileData):
    data_type: DataType = field(default=DataType.raster, init=False)
    layer_in_file: str  # name of layer in gpkg


@dataclass
class RanaVectorPublicationFileData(RanaPublicationFileData):
    data_type: DataType = field(default=DataType.vector, init=False)
    layer_in_file: str  # name of layer in gpkg
