import copy
import json
import math
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from bridgestyle.mapboxgl.fromgeostyler import convertGroup
from bridgestyle.qgis import togeostyler
from qgis.core import QgsMapLayer, QgsTask
from qgis.PyQt.QtCore import QObject, pyqtSignal

from rana_qgis_plugin.utils.api import (
    upload_file_styling,
    upload_publication_style,
)
from rana_qgis_plugin.utils.data_models import DataType, StyleUploadItem
from rana_qgis_plugin.utils.generic import (
    image_to_bytes,
)
from rana_qgis_plugin.utils.lizard import import_from_geostyler
from rana_qgis_plugin.utils.qgis import strip_rana_properties_from_qml
from rana_qgis_plugin.workers.style_layers import LayerSource


@dataclass
class PreparedStyle:
    """Plain styling data built on the main thread and written out by the worker.

    Holds only bytes, strings and dicts so the upload task never touches QGIS
    layers, renderers or bridgestyle.
    """

    qml_files: dict[str, bytes] = field(default_factory=dict)
    json_files: list[tuple[str, str | dict]] = field(default_factory=list)
    png_files: list[tuple[str, bytes]] = field(default_factory=list)


@dataclass
class PreparedStyleItem:
    """One style upload with its styling already prepared, or the reason it failed."""

    file_ref_str: str
    upload_func: Any
    style: PreparedStyle | None = None
    error: str | None = None


class StyleBuilder(QObject):
    """Style builder takes care of collecting style data; it is unaware of any context.

    ``prepare`` must run on the main thread: it reads live QGIS layers and calls
    bridgestyle, which are not safe to use from a worker thread.
    """

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(
        self, local_file_path: str, file_ref_str: str, layer_source: LayerSource
    ):
        super().__init__()
        self.local_file_path = local_file_path
        self.file_ref_str = file_ref_str
        self.layer_source = layer_source

    def prepare(self) -> PreparedStyle:
        raise NotImplementedError

    @property
    def layers(self) -> list[QgsMapLayer]:
        return self.layer_source.layers

    def validate_layers(self) -> bool:
        raise NotImplementedError

    def qml_bytes(self, layer: QgsMapLayer, scratch_dir: Path) -> bytes:
        qml_path = scratch_dir.joinpath("style.qml")
        layer.saveNamedStyle(str(qml_path))
        strip_rana_properties_from_qml(qml_path)
        return qml_path.read_bytes()


class RasterStyleBuilder(StyleBuilder):
    def validate_layers(self) -> bool:
        return len(self.layers) == 1

    def prepare(self) -> PreparedStyle:
        style = PreparedStyle()
        qml_name = Path(self.local_file_path).with_suffix(".qml").name
        with tempfile.TemporaryDirectory() as scratch_dir:
            style.qml_files[qml_name] = self.qml_bytes(
                self.layers[0], Path(scratch_dir)
            )
        lizard_styling = self._lizard_styling()
        if lizard_styling is not None:
            style.json_files.append(("colormap", lizard_styling))
        return style

    def _lizard_styling(self) -> Optional[dict]:
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
        return lizard_styling


class VectorStyleBuilder(StyleBuilder):
    def prepare(self) -> PreparedStyle:
        style = PreparedStyle()
        with tempfile.TemporaryDirectory() as scratch_dir:
            for layer in self.layers:
                style.qml_files[f"{layer.name()}.qml"] = self.qml_bytes(
                    layer, Path(scratch_dir)
                )
        self._add_qgis_styling(style)
        return style

    def _add_qgis_styling(self, style: PreparedStyle) -> None:
        # Convert QGIS layers to styling for the Rana Web Client
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
            return
        style.json_files.append(("style", mb_style))
        if sprite_sheet and sprite_sheet.get("img") and sprite_sheet.get("img2x"):
            style.json_files.append(("sprite", sprite_sheet["json"]))
            style.json_files.append(("sprite@2x", sprite_sheet["json2x"]))
            style.png_files.append(("sprite", image_to_bytes(sprite_sheet["img"])))
            style.png_files.append(("sprite@2x", image_to_bytes(sprite_sheet["img2x"])))


class VectorStyleBuilderAllLayers(VectorStyleBuilder):
    """Collects style files for all layers in a vector file."""

    def validate_layers(self) -> bool:
        return len(self.layers) > 0


class VectorStyleBuilderSingleLayer(VectorStyleBuilder):
    """Collects style files for a single layer in a vector file."""

    def __init__(
        self,
        local_file_path: str,
        file_ref_str: str,
        layer_source: LayerSource,
        layer_in_file: str,
    ):
        super().__init__(local_file_path, file_ref_str, layer_source)
        self.layer_in_file = layer_in_file

    @property
    def layers(self) -> list[QgsMapLayer]:
        layer = next(
            (layer for layer in super().layers if layer.name() == self.layer_in_file),
            None,
        )
        return [layer] if layer else []

    def validate_layers(self) -> bool:
        return len(self.layers) == 1


def make_builder(item: StyleUploadItem) -> StyleBuilder:
    """Build the appropriate StyleBuilder based on data_type."""
    if item.layer_source is None:
        raise RuntimeError(f"No layers captured for {item.file_ref_str}")
    if item.data_type == DataType.raster:
        return RasterStyleBuilder(
            item.local_file_path, item.file_ref_str, item.layer_source
        )
    elif item.data_type == DataType.vector:
        if item.layer_in_file:
            return VectorStyleBuilderSingleLayer(
                item.local_file_path,
                item.file_ref_str,
                item.layer_source,
                item.layer_in_file,
            )
        return VectorStyleBuilderAllLayers(
            item.local_file_path, item.file_ref_str, item.layer_source
        )
    else:
        raise ValueError(
            f"Unsupported data type for style upload: {item.data_type.value}"
        )


def prepare_style_item(item: StyleUploadItem) -> PreparedStyleItem:
    """Convert one item's layers to plain styling data. Must run on the main thread.

    Failures are captured on the result rather than raised, so the upload task
    reports them per item exactly like worker-side failures.
    """
    name = item.file_ref_str
    try:
        builder = make_builder(item)
        if not builder.validate_layers():
            raise RuntimeError(f"Layer not found for {name}")
        return PreparedStyleItem(name, item.upload_func, style=builder.prepare())
    except Exception as error:
        return PreparedStyleItem(name, item.upload_func, error=str(error))
    finally:
        if item.layer_source is not None:
            item.layer_source.discard()


def prepare_style_items(items: list[StyleUploadItem]) -> list[PreparedStyleItem]:
    """Prepare every item on the main thread before the upload task is started."""
    return [prepare_style_item(item) for item in items]


def write_style_files(style: PreparedStyle, directory: Path) -> list[tuple]:
    """Write prepared styling into ``directory`` and describe the files for upload."""
    files: list[tuple[str, str, str, str]] = []
    zip_path = directory.joinpath("qml.zip")
    with zipfile.ZipFile(zip_path, "w") as zip_file:
        for name, content in style.qml_files.items():
            zip_file.writestr(name, content)
    files.append(("files", "qml.zip", str(zip_path), "application/zip"))
    for name, payload in style.json_files:
        json_path = directory.joinpath(name).with_suffix(".json")
        with open(json_path, "w") as f:
            if isinstance(payload, str):
                f.write(payload)
            else:
                json.dump(payload, f)
        files.append(("files", json_path.name, str(json_path), "application/json"))
    for name, data in style.png_files:
        png_path = directory.joinpath(name).with_suffix(".png")
        png_path.write_bytes(data)
        files.append(("files", png_path.name, str(png_path), "image/png"))
    return files


class StyleUploadTask(QgsTask):
    """Write and upload prepared styles for one or more items.

    Runs on a worker thread: it only touches plain data and the filesystem.
    """

    item_finished = pyqtSignal(str)
    item_started = pyqtSignal(str)
    item_failed = pyqtSignal(str, str)
    warning = pyqtSignal(str)

    def __init__(self, items: list[PreparedStyleItem]):
        # avoid importing task flags for typing compatibility in tests
        super().__init__("Upload styling")
        self.items = items
        self.failed_items: list[tuple[str, str]] = []
        self.rana_sync_keys: list[tuple[str, str]] = []

    def run(self) -> bool:
        for index, item in enumerate(self.items):
            if self.isCanceled():
                return False
            name = item.file_ref_str
            self.item_started.emit(name)
            try:
                if item.error is not None:
                    raise RuntimeError(item.error)
                if item.style is None:
                    raise RuntimeError(f"Styling was not prepared for {name}")
                with tempfile.TemporaryDirectory() as directory:
                    files = write_style_files(item.style, Path(directory))
                    if not files:
                        raise RuntimeError(f"No style files generated for {name}")
                    item.upload_func(files)
                self.item_finished.emit(name)
            except Exception as error:
                self.failed_items.append((name, str(error)))
                self.item_failed.emit(name, str(error))
            self.setProgress((index + 1) * 100 / len(self.items))
        return not self.failed_items


def discard_layer_sources(items: list[StyleUploadItem]) -> None:
    """Release captured layer snapshots for items that will never be built."""
    for item in items:
        if item.layer_source is not None:
            item.layer_source.discard()


def make_publication_style_upload_item(
    publication_id: str,
    publication_version: str,
    data_type: DataType,
    local_file_path: str,
    file_ref_str: str,
    file_path: str,
    layer_source: LayerSource,
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
        layer_source=layer_source,
    )


def make_file_style_upload_item(
    descriptor_id: str,
    data_type: DataType,
    local_file_path: str,
    file_ref_str: str,
    layer_source: LayerSource,
    layer_in_file: str | None = None,
    project_id: str | None = None,
    file_id: str | None = None,
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
        file_id=file_id,
        layer_source=layer_source,
    )
