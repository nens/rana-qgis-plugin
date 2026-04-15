import copy
import json
import math
import shutil
import tempfile
import time
import zipfile
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Any

import requests
from bridgestyle.mapboxgl.fromgeostyler import convertGroup
from bridgestyle.qgis import togeostyler
from qgis.core import QgsProject
from qgis.PyQt.QtCore import QObject, QSettings, Qt, QThread, pyqtSignal, pyqtSlot

from rana_qgis_plugin.constant import STYLE_DIR
from rana_qgis_plugin.utils.api import (
    RanaResourceNotFound,
    RanaUploadError,
    upload_file_styling,
    upload_publication_style,
)
from rana_qgis_plugin.utils.data_models import DataType, RanaPublicationFileData
from rana_qgis_plugin.utils.generic import (
    get_local_publication_file_path,
    image_to_bytes,
)
from rana_qgis_plugin.utils.lizard import import_from_geostyler


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
        all_layers = QgsProject.instance().mapLayers().values()
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
        return [zip_files, lizard_styling_files]

    def _save_lizard_style_to_file(self) -> tuple:
        layer = self.layers[0]
        geostyler, _, _, warnings = togeostyler.convert(layer)
        if len(geostyler["rules"]) != 1:
            self.failed.emit(f"Multiple rules found for {self.file_ref_str}.")
            return
        if len(geostyler["rules"][0]["symbolizers"]) != 1:
            self.failed.emit(f"Multiple symbolizers found for {self.file_ref_str}.")
            return
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
                    return
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
        files = []
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


class FileDescriptorStyleUploadWorker(QThread):
    """Upload style for a single file descriptor.

    Selects the appropriate StyleBuilder based on data_type and uploads
    the resulting style files via the unified upload_file_styling endpoint.
    """

    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)
    retry = pyqtSignal(str)  # Signal to show busy progress bar with message

    def __init__(
        self,
        descriptor_id: str,
        data_type: DataType,
        local_file_path: str,
        file_ref_str: str,
        communication,
        retry_timeout_seconds: int = 0,
    ):
        super().__init__()
        self.success = True
        self.descriptor_id = descriptor_id
        self.data_type = data_type
        self.local_file_path = local_file_path
        self.file_ref_str = file_ref_str
        self.communication = communication
        self.retry_timeout_seconds = retry_timeout_seconds

    def _make_builder(self) -> StyleBuilder:
        """Build the appropriate StyleBuilder based on data_type."""
        if self.data_type == DataType.raster:
            return RasterStyleBuilder(self.local_file_path, self.file_ref_str)
        elif self.data_type == DataType.vector:
            return VectorStyleBuilderAllLayers(self.local_file_path, self.file_ref_str)
        elif self.data_type == DataType.schematisation:
            return SchematisationStyleBuilder()
        else:
            raise ValueError(
                f"Unsupported data type for style upload: {self.data_type.value}"
            )

    def mark_as_failed(self, msg: str):
        self.success = False
        self.failed.emit(msg)

    def _upload_with_retry(self, files):
        start_time = time.time()
        retry_delay = 2  # seconds between retries
        # Signal to show busy progress bar
        self.retry.emit("Waiting for style upload...")
        while True:
            elapsed_time = time.time() - start_time
            if elapsed_time >= self.retry_timeout_seconds:
                self.mark_as_failed(
                    f"Uploading styling files failed: Endpoint not ready after {self.retry_timeout_seconds} seconds"
                )
                break
            try:
                upload_file_styling(self.descriptor_id, files)
                break
            except RanaResourceNotFound:
                time.sleep(retry_delay)
            except RanaUploadError as e:
                self.mark_as_failed(f"Uploading styling files failed: {e}")
                break

    def run(self):
        """Build style files and upload them via upload_file_styling endpoint."""
        builder = self._make_builder()
        builder.failed.connect(self.mark_as_failed)
        builder.warning.connect(self.warning.emit)

        if not builder.validate_layers():
            self.failed.emit(
                f"Layer not found for {self.file_ref_str}. Add file to map and try again"
            )
            return

        builder.tempdir.mkdir(parents=True, exist_ok=True)
        files = builder.get_files()

        if self.success and files:
            try:
                upload_file_styling(self.descriptor_id, files)
            except RanaResourceNotFound as e:
                if self.retry_timeout_seconds > 0:
                    self._upload_with_retry(files)
                else:
                    self.mark_as_failed(f"Uploading styling files failed: {e}")
            except RanaUploadError as e:
                self.mark_as_failed(f"Uploading styling files failed: {e}")

        builder.clean()

        if self.success:
            self.finished.emit(
                f"Styling files uploaded successfully for {self.file_ref_str}."
            )


class PublicationStyleUploadWorker(QThread):
    """Handle uploading many styles associated to single publication version"""

    finished = pyqtSignal(str, list)
    progress = pyqtSignal(int)

    def __init__(
        self,
        project: dict,
        publication_version: dict,
        tasks: list[RanaPublicationFileData],
        communication,
    ):
        super().__init__()
        self.communication = communication
        self.project = project
        self.publication_version = publication_version
        self.tasks = tasks
        self.warning_cnt = 0
        self.fail_cnt = 0

    @pyqtSlot(str)
    def pass_fail_to_logging(self, msg):
        self.communication.log_err(msg)
        self.fail_cnt += 1

    @pyqtSlot(str)
    def pass_warning_to_logging(self, msg):
        self.communication.log_warn(msg)
        self.warning_cnt += 1

    @contextmanager
    def builder_signal_connections(self, builder: StyleBuilder):
        connections = [
            (builder.failed, self.pass_fail_to_logging),
            (builder.warning, self.pass_warning_to_logging),
        ]
        """Context manager to ensure signals are always connected and disconnected properly."""
        for signal, func in connections:
            signal.connect(func)
        try:
            yield
        finally:
            for signal, func in connections:
                try:
                    signal.disconnect(func)
                except TypeError:
                    # TypeError is raised when signal is not connected
                    continue

    def _make_builder(self, task) -> StyleBuilder:
        if task.data_type not in [DataType.raster, DataType.vector]:
            raise ValueError(f"Unknown file type: {task.data_type.value}")
        local_file_path = get_local_publication_file_path(
            self.project["slug"], task.file["id"], task.file_tree
        )
        file_ref_str = f"layer {task.display_name} from {'/'.join(task.file_tree)}"
        if task.data_type == DataType.raster:
            return RasterStyleBuilder(local_file_path, file_ref_str)
        elif task.data_type == DataType.vector:
            return VectorStyleBuilderSingleLayer(
                local_file_path, file_ref_str, task.layer_in_file
            )

    def run(self):
        not_found_cnt = 0
        new_style_ids = []
        for i, task in enumerate(self.tasks):
            self.progress.emit(i)
            try:
                builder = self._make_builder(task)
            except ValueError:
                not_found_cnt += 1
                continue
            with self.builder_signal_connections(builder):
                if not builder.validate_layers():
                    not_found_cnt += 1
                    continue
                builder.tempdir.mkdir(parents=True, exist_ok=True)
                files = builder.get_files()
            if files:
                try:
                    style_id = upload_publication_style(
                        publication_id=self.publication_version["publication_id"],
                        publication_version=self.publication_version["version"],
                        file_path=task.file["id"],
                        files=files,
                    )
                    new_style_ids.append((task, style_id))
                except RanaUploadError as e:
                    # mark as failed and continue with clean up
                    self.pass_fail_to_logging(f"Failed to upload styling files: {e}")
            # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
            try:
                shutil.rmtree(builder.tempdir)
            except (FileNotFoundError, PermissionError, OSError) as e:
                pass
        if len(new_style_ids) > 0:
            msg = f"Styling file(s) uploaded successfully for {len(new_style_ids)} layer(s)."
        else:
            msg = "No styling files uploaded."
        if not_found_cnt > 0:
            msg += f"\n{not_found_cnt} layer(s) not found. Add layer(s) to map and try again."
        if self.fail_cnt > 0:
            msg += f"\nUpload failed for {self.fail_cnt} layer(s), see the logs for more information."
        if self.warning_cnt > 0:
            msg += f"\n{self.warning_cnt} warnings were generated, see the logs for more information."
        self.finished.emit(msg, new_style_ids)
