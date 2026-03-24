from dataclasses import dataclass
from typing import Optional


@dataclass
class RanaFileData:
    file: dict
    file_tree: list[str]


@dataclass
class RanaVectorPublicationFileData(RanaFileData):
    layer_in_file: str  # name of layer in gpkg
    display_name: str  # name for layer in Qgis layer panel
    publication_version: int
    style_id: Optional[str] = None


@dataclass
class RanaRasterPublicationFileData(RanaFileData):
    display_name: str  # name for layer in Qgis layer panel
    publication_version: int
    style_id: Optional[str] = None
