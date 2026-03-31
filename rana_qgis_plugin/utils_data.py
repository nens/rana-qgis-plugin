from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class DataType(Enum):
    raster = "raster"
    vector = "vector"
    schematisation = "threedi-schematisation"

    @classmethod
    def from_value(cls, value: str) -> Optional["DataType"]:
        if value in cls._value2member_map_:
            return cls._value2member_map_[value]
        return None


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
