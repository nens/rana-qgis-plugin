import copy
import json
import math
import shutil
import tempfile
import zipfile
from functools import cached_property
from pathlib import Path
from typing import Any, Optional

import requests
from bridgestyle.mapboxgl.fromgeostyler import convertGroup
from bridgestyle.qgis import togeostyler
from qgis.core import QgsProject, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal

from rana_qgis_plugin.constant import STYLE_DIR
from rana_qgis_plugin.utils.api import (
    upload_file_styling,
    upload_publication_style,
)
from rana_qgis_plugin.utils.data_models import DataType, StyleUploadItem
from rana_qgis_plugin.utils.generic import (
    image_to_bytes,
)
from rana_qgis_plugin.utils.lizard import import_from_geostyler
from rana_qgis_plugin.utils.local_paths import get_local_publication_file_path


class StyleBuilder(QObject):
    """Style builder takes care of collecting style files; it is unaware of any context"""

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, local_file_path: str, file_ref_str: str):
        super().__init__()
        self.local_file_path = local_file_path
        self.file_ref_str = file_ref_str

    def get_files(self) -> list:
        raise NotImplementedError

    def clean(self):
        # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
        try:
            shutil.rmtree(self.tempdir)
        except (FileNotFoundError, PermissionError, OSError) as e:
            pass

    @cached_property
    def tempdir(self) -> Path:
        return Path(tempfile.mkdtemp())

    @cached_property
    def all_layers(self):
        proj = QgsProject.instance()
        if proj is None:
            return []
        all_layers = proj.mapLayers().values()
        return [layer for layer in all_layers if self.local_file_path in layer.source()]

    @property
    def layers(self):
        return self.all_layers

    def validate_layers(self) -> bool:
        raise NotImplementedError

    def _create_qml_zip(self, zip_path: str):
        """Craete a QML zip file for all the qml files in the local directory"""
        try:
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for file_path in self.tempdir.rglob("*.qml"):
                    zip_file.write(file_path, file_path.relative_to(self.tempdir))
        except Exception as e:
            self.failed.emit(f"Failed to create QML zip: {str(e)}")

    def layer_qml_path(self, layer_name: str) -> Path:
        return self.tempdir.joinpath(f"{layer_name}.qml")

    def save_qml_style_to_file(self) -> tuple:
        # Save QML style files for each layer to local directory
        for layer in self.layers:
            # TODO: this breaks with non writable paths due to illegal characters
            qml_path = self.layer_qml_path(layer.name())
            layer.saveNamedStyle(str(qml_path))
        zip_path = str(self.tempdir.joinpath("qml.zip"))
        self._create_qml_zip(zip_path)
        return ("files", "qml.zip", zip_path, "application/zip")


class SchematisationStyleBuilder(StyleBuilder):
    """Export predefined style for a schematisation"""

    def __init__(self):
        super().__init__("", "")

    def clean(self):
        # Do not clean up these files!
        pass

    def validate_layers(self) -> bool:
        # qgis layers are not relevant
        return True

    def get_files(self) -> list:
        base_path = STYLE_DIR.joinpath("schematisation")
        files = [
            ("files", "qml.zip", str(base_path.joinpath("qml.zip")), "application/zip")
        ]
        for name in ["sprite.json", "sprite@2x.json", "style.json"]:
            files.append(
                ("files", name, str(base_path.joinpath(name)), "application/json")
            )
        for name in ["sprite.png", "sprite@2x.png"]:
            files.append(("files", name, str(base_path.joinpath(name)), "image/png"))
        return files


class RasterStyleBuilder(StyleBuilder):
    def validate_layers(self) -> bool:
        return len(self.layers) == 1

    def layer_qml_path(self, layer_name: str) -> Path:
        return self.tempdir.joinpath(
            Path(self.local_file_path).with_suffix(".qml").name
        )

    def get_files(self) -> list:
        zip_files = self.save_qml_style_to_file()
        lizard_styling_files = self._save_lizard_style_to_file()
        if lizard_styling_files:
            return [zip_files, lizard_styling_files]
        return [zip_files]

    def _save_lizard_style_to_file(self) -> Optional[tuple]:
        layer = self.layers[0]
        geostyler, _, _, warnings = togeostyler.convert(layer)
        if len(geostyler["rules"]) != 1:
            self.failed.emit(f"Multiple rules found for {self.file_ref_str}.")
            return None
        if len(geostyler["rules"][0]["symbolizers"]) != 1:
            self.failed.emit(f"Multiple symbolizers found for {self.file_ref_str}.")
            return None
        lizard_styling = import_from_geostyler(geostyler["rules"][0]["symbolizers"][0])
        # Do some corrections and checks
        labels = copy.deepcopy(lizard_styling.get("labels", {}))
        for language, ranges in labels.items():
            new_labels = []
            for quantity, label in ranges:
                if math.isinf(quantity):
                    warnings.append(
                        f"Label '{label}' with infinite quantity cannot be used and will be ignored."
                    )
                else:
                    new_labels.append([quantity, label])
            lizard_styling["labels"][language] = new_labels
        if lizard_styling["type"] == "DiscreteColormap":
            for entry, _ in lizard_styling["data"]:
                if isinstance(entry, float):
                    self.failed.emit(
                        f"Failed to generate and upload styling files: DiscreteColormap cannot contain float quantities."
                    )
                    return None
        if warnings:
            self.warning.emit(", ".join(set(warnings)))
        lizard_styling_path = self.tempdir.joinpath("colormap.json")
        with open(lizard_styling_path, "w") as f:
            json.dump(lizard_styling, f)
        return ("files", "colormap.json", str(lizard_styling_path), "application/json")


class VectorStyleBuilder(StyleBuilder):
    def get_files(self) -> list:
        zip_path = self.save_qml_style_to_file()
        qgis_styling_files = self.get_qgis_styling_files()

        return [zip_path] + qgis_styling_files

    def _collect_json_files(self, json_data: list[tuple[str, dict]]) -> list:
        files = []
        for name, data in json_data:
            json_path = self.tempdir.joinpath(name).with_suffix(".json")
            with open(json_path, "w") as f:
                with open(json_path, "w") as f:
                    if isinstance(data, str):
                        f.write(data)
                    else:
                        json.dump(data, f)
            files.append(("files", json_path.name, str(json_path), "application/json"))
        return files

    def _collect_png_files(self, png_data: list[tuple[str, Any]]) -> list:
        files = []
        for name, img_data in png_data:
            png_path = self.tempdir.joinpath(name).with_suffix(".png")
            with open(png_path, "wb") as f:
                f.write(image_to_bytes(img_data))
            files.append(("files", png_path.name, str(png_path), "image/png"))
        return files

    def get_qgis_styling_files(self) -> list:
        files: list[tuple[str, str, str, str]] = []
        # Convert QGIS layers to styling files for the Rana Web Client
        try:
            _, warnings, mb_style, sprite_sheet = convertGroup(
                {"layers": [layer.name() for layer in self.layers]},
                {layer.name(): layer for layer in self.layers},
                "http://baseUrl",
                workspace="workspace",
                name="default",
            )
            if warnings:
                self.warning.emit(", ".join(set(warnings)))
        except Exception as e:
            self.failed.emit(f"Failed to convert local styling: {str(e)}")
            return files
        # Save styling to file
        files += self._collect_json_files([("style", mb_style)])
        # Save sprite sheet to file
        if sprite_sheet and sprite_sheet.get("img") and sprite_sheet.get("img2x"):
            files += self._collect_json_files(
                [
                    ("sprite", sprite_sheet["json"]),
                    ("sprite@2x", sprite_sheet["json2x"]),
                ],
            )
            files += self._collect_png_files(
                [
                    ("sprite", sprite_sheet["img"]),
                    ("sprite@2x", sprite_sheet["img2x"]),
                ],
            )
        return files


class VectorStyleBuilderAllLayers(VectorStyleBuilder):
    """Collects style files for all layers in a vector file."""

    def validate_layers(self) -> bool:
        return len(self.layers) > 0


class VectorStyleBuilderSingleLayer(VectorStyleBuilder):
    """Collects style files for a single layer in a vector file."""

    def __init__(self, local_file_path: str, file_ref_str: str, layer_in_file: str):
        super().__init__(local_file_path, file_ref_str)
        self.layer_in_file = layer_in_file

    @property
    def layers(self):
        layer = next(
            (layer for layer in super().layers if layer.name() == self.layer_in_file),
            None,
        )
        return [layer] if layer else []

    def validate_layers(self) -> bool:
        return len(self.layers) == 1


class StyleUploadTask(QgsTask):
    """Build and upload styles for one or more items."""

    item_finished = pyqtSignal(str)
    item_started = pyqtSignal(str)
    item_failed = pyqtSignal(str, str)
    warning = pyqtSignal(str)

    def __init__(self, items: list[StyleUploadItem]):
        # avoid importing task flags for typing compatibility in tests
        super().__init__("Upload styling")
        self.items = items
        self.failed_items: list[tuple[str, str]] = []
        self.rana_sync_keys: list[tuple[str, str]] = []

    def make_builder(self, item: StyleUploadItem) -> StyleBuilder:
        """Build the appropriate StyleBuilder based on data_type."""
        if item.data_type == DataType.raster:
            return RasterStyleBuilder(item.local_file_path, item.file_ref_str)
        elif item.data_type == DataType.vector:
            if item.layer_in_file:
                return VectorStyleBuilderSingleLayer(
                    item.local_file_path, item.file_ref_str, item.layer_in_file
                )
            return VectorStyleBuilderAllLayers(item.local_file_path, item.file_ref_str)
        elif item.data_type == DataType.schematisation:
            return SchematisationStyleBuilder()
        else:
            raise ValueError(
                f"Unsupported data type for style upload: {item.data_type.value}"
            )

    def run(self) -> bool:
        for index, item in enumerate(self.items):
            if self.isCanceled():
                return False
            name = item.file_ref_str
            self.item_started.emit(name)
            builder = None
            try:
                builder = self.make_builder(item)
                if not builder.validate_layers():
                    raise RuntimeError(f"Layer not found for {name}")
                builder.tempdir.mkdir(parents=True, exist_ok=True)
                files = builder.get_files()
                if not files:
                    raise RuntimeError(f"No style files generated for {name}")
                item.upload_func(files)
                self.item_finished.emit(name)
            except Exception as error:
                self.failed_items.append((name, str(error)))
                self.item_failed.emit(name, str(error))
            finally:
                if builder is not None:
                    builder.clean()
            self.setProgress((index + 1) * 100 / len(self.items))
        return not self.failed_items


def make_publication_style_upload_item(
    publication_id: str,
    publication_version: str,
    data_type: DataType,
    local_file_path: str,
    file_ref_str: str,
    file_path: str,
    layer_in_file: str | None = None,
) -> StyleUploadItem:

    def upload_func(files: list) -> object:
        return upload_publication_style(
            publication_id=publication_id,
            publication_version=publication_version,
            file_path=file_path,
            files=files,
        )

    return StyleUploadItem(
        data_type=data_type,
        local_file_path=local_file_path,
        file_ref_str=file_ref_str,
        upload_func=upload_func,
        layer_in_file=layer_in_file,
    )


def make_file_style_upload_item(
    descriptor_id: str,
    data_type: DataType,
    local_file_path: str,
    file_ref_str: str,
    layer_in_file: str | None = None,
    project_id: str | None = None,
) -> StyleUploadItem:
    """Build a style item for the file-descriptor styling endpoint."""

    def upload_func(files: list) -> object:
        return upload_file_styling(descriptor_id, files)

    return StyleUploadItem(
        data_type=data_type,
        local_file_path=local_file_path,
        file_ref_str=file_ref_str,
        upload_func=upload_func,
        layer_in_file=layer_in_file,
        project_id=project_id,
        descriptor_id=descriptor_id,
    )
