import copy
import json
import math
import shutil
import tempfile
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

from rana_qgis_plugin.utils import get_publication_layer_path, image_to_bytes
from rana_qgis_plugin.utils_api import (
    FetchError,
    get_vector_style_upload_urls,
    upload_publication_style,
    upload_raster_styling,
)
from rana_qgis_plugin.utils_data import DataType, RanaPublicationFileData
from rana_qgis_plugin.utils_lizard import import_from_geostyler


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

    @cached_property
    def tempdir(self) -> Path:
        import uuid
        # return Path.home().joinpath("temp", 'rana', uuid.uuid4().hex)
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

    def save_qml_style_to_file(self) -> tuple:
        # Save QML style files for each layer to local directory
        for layer in self.layers:
            # TODO: this breaks with non writable paths due to illegal characters
            qml_path = self.tempdir.joinpath(f"{layer.name()}.qml")
            layer.saveNamedStyle(str(qml_path))
        zip_path = str(self.tempdir.joinpath("qml.zip"))
        self._create_qml_zip(zip_path)
        return ("files", "qml.zip", zip_path, "application/zip")


class RasterStyleBuilder(StyleBuilder):
    def validate_layers(self) -> bool:
        return len(self.layers) == 1

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
    def __init__(self, local_file_path: str, file_ref_str: str, layer_in_file: str):
        super().__init__(local_file_path, file_ref_str)
        self.layer_in_file = layer_in_file

    def get_files(self) -> list:
        zip_path = self.save_qml_style_to_file()
        qgis_styling_files = self.get_qgis_styling_files()
        return [zip_path] + qgis_styling_files

    @property
    def layers(self):
        return [self.layer] if self.layer else []

    @cached_property
    def layer(self):
        return next(
            (layer for layer in super().layers if layer.name() == self.layer_in_file),
            None,
        )

    def validate_layers(self) -> bool:
        return self.layer is not None

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
                {"layers": [self.layer.name()]},
                {self.layer.name(): self.layer},
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


class VectorStyleBuilderOld(StyleBuilder):
    """Collects style files for all layers in a vector file."""

    def get_files(self) -> list:
        return [self.save_qml_style_to_file()]

    def validate_layers(self) -> bool:
        return len(self.layers) > 0


class StyleUploader(QObject):
    """The StyleUploader takes care of uploading files generated by builder and is aware of the context"""

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def upload_to_rana(self, files):
        raise NotImplementedError


class RasterFileDescriptorStyleUploader(StyleUploader):
    """Uploads style for a single raster file to the old raster specific endpoint"""

    def __init__(
        self,
        file_descriptor_id: str,
    ):
        super().__init__()
        self.descriptor_id = file_descriptor_id

    def upload_to_rana(self, files):
        try:
            upload_raster_styling(self.descriptor_id, files)
        except Exception as e:
            self.failed.emit(f"Uploading styling files failed: {e}")


class VectorFileDescriptorStyleUploader(StyleUploader):
    """Uploads style for all layers in a vector file to the old vector specific"""

    def __init__(
        self,
        file_descriptor_id: str,
        builder: VectorStyleBuilder,
    ):
        super().__init__()
        # builder is added to class because this still uses the old s3 upload which prevents decoupling building and upload
        self.builder = builder
        self.descriptor_id = file_descriptor_id

    def upload_to_rana(self, files):
        qgis_layers = {layer.name(): layer for layer in self.builder.layers}
        group = {"layers": list(qgis_layers.keys())}
        base_url = "http://baseUrl"

        # Convert QGIS layers to styling files for the Rana Web Client
        try:
            _, warnings, mb_style, sprite_sheet = convertGroup(
                group, qgis_layers, base_url, workspace="workspace", name="default"
            )
            if warnings:
                self.warning.emit(", ".join(set(warnings)))

            # Get upload URLs to S3
            upload_urls = get_vector_style_upload_urls(self.descriptor_id)

            if not upload_urls:
                self.failed.emit("Failed to get vector style upload URLs from the API.")
                return

            # Upload style.json
            self._upload_to_s3(
                upload_urls["style.json"],
                json.dumps(mb_style).replace(r"\\n", r"\n").replace(r"\\t", r"\t"),
                "application/json",
            )

            # Upload sprite images if available
            if sprite_sheet and sprite_sheet.get("img") and sprite_sheet.get("img2x"):
                self._upload_to_s3(
                    upload_urls["sprite.png"],
                    image_to_bytes(sprite_sheet["img"]),
                    "image/png",
                )
                self._upload_to_s3(
                    upload_urls["sprite@2x.png"],
                    image_to_bytes(sprite_sheet["img2x"]),
                    "image/png",
                )
                self._upload_to_s3(
                    upload_urls["sprite.json"], sprite_sheet["json"], "application/json"
                )
                self._upload_to_s3(
                    upload_urls["sprite@2x.json"],
                    sprite_sheet["json2x"],
                    "application/json",
                )
            # Zip and upload QML zip
            zip_path = files[0][2]
            with open(zip_path, "rb") as file:
                self._upload_to_s3(upload_urls["qml.zip"], file, "application/zip")
        except Exception as e:
            self.failed.emit(f"Failed to upload styling files: {str(e)}")

    def _upload_to_s3(self, url: str, data: dict, content_type: str):
        """Method to upload to S3"""
        try:
            headers = {"Content-Type": content_type}
            response = requests.put(url, data=data, headers=headers)
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            self.failed.emit(f"Failed to upload file to S3: {str(e)}")


class FileDescriptorStyleUploadWorker(QThread):
    """Handle uploading style via file descriptor"""

    # TODO:
    # Once new endpoints are ready for use we no longer need different uploaders
    # and move the uploader functionality to this class.

    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, uploader: StyleUploader, builder: StyleBuilder, communication):
        super().__init__()
        self.communication = communication
        self.uploader = uploader
        self.builder = builder
        self.success = True
        # Connect signals from uploader and builder
        self.uploader.warning.connect(self.warning.emit)
        self.builder.warning.connect(self.warning.emit)
        self.uploader.failed.connect(
            self.mark_as_failed, Qt.ConnectionType.DirectConnection
        )
        self.builder.failed.connect(
            self.mark_as_failed, Qt.ConnectionType.DirectConnection
        )

    def mark_as_failed(self, msg):
        self.success = False
        self.failed.emit(msg)

    # def _make_builder(self, task) -> StyleBuilder:

    def run(self):
        if not self.builder.validate_layers():
            self.failed.emit(
                f"Layer not found for {self.file_ref_str}. Add file to map and try again"
            )
            return
        self.builder.tempdir.mkdir(parents=True, exist_ok=True)
        files = self.builder.get_files()
        self.uploader.upload_to_rana(files)
        # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
        try:
            shutil.rmtree(self.builder.tempdir)
        except (FileNotFoundError, PermissionError, OSError) as e:
            pass
        if self.success:
            self.finished.emit(
                f"Styling files uploaded successfully for {self.builder.file_ref_str}."
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
        _, local_file_path = get_publication_layer_path(
            self.project["slug"], task.file["id"], task.file_tree
        )
        file_ref_str = f"layer {task.display_name} from {'/'.join(task.file_tree)}"
        if task.data_type == DataType.raster:
            return RasterStyleBuilder(local_file_path, file_ref_str)
        elif task.data_type == DataType.vector:
            return VectorStyleBuilder(local_file_path, file_ref_str, task.layer_in_file)

    def run(self):
        not_fount_cnt = 0
        new_style_ids = []
        for i, task in enumerate(self.tasks):
            self.progress.emit(i)
            try:
                builder = self._make_builder(task)
            except ValueError:
                not_fount_cnt += 1
                continue
            with self.builder_signal_connections(builder):
                if not builder.validate_layers():
                    not_fount_cnt += 1
                    continue
                builder.tempdir.mkdir(parents=True, exist_ok=True)
                files = builder.get_files()
            if files:
                from qgis.core import Qgis, QgsMessageLog

                # QgsMessageLog.logMessage(f"{files=}", "DEBUG", Qgis.Info)

                # TODO: fix upload_publication_styling once I understand what "ref" is
                try:
                    style_id = upload_publication_style(
                        publication_id=self.publication_version["publication_id"],
                        publication_version=self.publication_version["version"],
                        file_path=task.file["id"],
                        files=files,
                    )
                    new_style_ids.append((task, style_id))
                    from qgis.core import Qgis, QgsMessageLog

                    # QgsMessageLog.logMessage(f"{files=}", "DEBUG", Qgis.Info)

                    QgsMessageLog.logMessage(
                        f'Uploaded styling: {self.publication_version["publication_id"]=}; {style_id=}; {self.publication_version["version"]=}',
                        "DEBUG",
                        Qgis.Info,
                    )
                except FetchError as e:
                    # mark as failed and continue with clean up
                    self.pass_fail_to_logging(f"Failed to upload styling files: {e}")
            # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
            try:
                shutil.rmtree(builder.tempdir)
            except (FileNotFoundError, PermissionError, OSError) as e:
                pass
        if len(new_style_ids) > 0:
            msg = (
                f"Styling files uploaded successfully for {len(new_style_ids)} layers."
            )
        else:
            msg = "No styling files uploaded."
        if not_fount_cnt > 0:
            msg += (
                f"\n{not_fount_cnt} layers not found. Add layers to map and try again."
            )
        if self.fail_cnt > 0:
            msg += "\nUpload failed for {self.fail_cnt} layers, see the logs for more information."
        if self.warning_cnt > 0:
            msg += f"\n{self.warning_cnt} warnings were generated, see the logs for more information."
        self.finished.emit(msg, new_style_ids)
