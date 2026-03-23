from dataclasses import dataclass
from typing import Optional


@dataclass
class RanaFileData:
    file: dict
    file_tree: list[str]


@dataclass
class RanaVectorFileData(RanaFileData):
    layer_in_file: str  # name of layer in gpkg
    display_name: str  # name for layer in Qgis layer panel
    style_id: Optional[str] = None


@dataclass
class RanaRasterFileData(RanaFileData):
    display_name: str  # name for layer in Qgis layer panel
    style_id: Optional[str] = None
