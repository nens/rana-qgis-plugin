import copy
import json
import math
import os
import shutil
import tempfile
import zipfile
from contextlib import contextmanager
from functools import cached_property
from pathlib import Path
from typing import Optional

import requests
from bridgestyle.mapboxgl.fromgeostyler import convertGroup
from bridgestyle.qgis import togeostyler
from qgis.core import QgsProject
from qgis.PyQt.QtCore import (
    QObject,
    QSettings,
    QThread,
    pyqtSignal,
)

from rana_qgis_plugin.utils import (
    get_local_file_path,
    get_publication_layer_path,
    image_to_bytes,
)
from rana_qgis_plugin.utils_api import (
    get_vector_style_upload_urls,
    upload_publication_style,
    upload_raster_styling,
)
from rana_qgis_plugin.utils_lizard import import_from_geostyler


class StyleBuilder(QObject):
    """Style builder takes care of collecting style files; it is unaware of any context"""

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, local_file_path: str, file_ref_str: str):
        super().__init__()
        self.local_file_path = local_file_path
        self.file_ref_str = file_ref_str

    @cached_property
    def tempdir(self) -> str:
        return tempfile.mkdtemp()

    @cached_property
    def layers(self):
        all_layers = QgsProject.instance().mapLayers().values()
        return [layer for layer in all_layers if self.local_file_path in layer.source()]

    def validate_layers(self) -> bool:
        raise NotImplementedError

    def save_qml_style_to_file(self) -> str:
        raise NotImplementedError

    def get_files(self) -> list:
        raise NotImplementedError


class RasterStyleBuilder(StyleBuilder):
    def validate_layers(self) -> bool:
        if not self.layers:
            self.failed.emit(
                f"No layers found for {self.file_ref_str}. Open the file in QGIS and try again."
            )
            return False
        elif not len(self.layers) == 1:
            self.failed.emit(
                f"Multiple layers found for {self.file_ref_str}. Open the file in QGIS and try again."
            )
            return False
        return True

    def save_qml_style_to_file(self) -> str:
        layer = self.layers[0]
        qml_file_name = Path(layer.name()).with_suffix(".qml").name
        qml_path = str(Path(self.tempdir).joinpath(qml_file_name))
        # qml_path = os.path.join(self.tempdir, qml_file_name)
        layer.saveNamedStyle(str(qml_path))
        zip_path = os.path.join(self.tempdir, "qml.zip")
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(qml_path, qml_file_name)
        return zip_path

    def get_files(self) -> list:
        zip_path = self.save_qml_style_to_file()
        lizard_styling_path = self._save_lizard_style_to_file()
        return [
            ("files", "colormap.json", lizard_styling_path, "application/json"),
            ("files", "qml.zip", zip_path, "application/zip"),
        ]

    def _save_lizard_style_to_file(self):
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
        lizard_styling_path = os.path.join(self.tempdir, "colormap.json")
        with open(lizard_styling_path, "w") as f:
            json.dump(lizard_styling, f)
        return lizard_styling_path


class VectorStyleBuilder(StyleBuilder):
    def __init__(self, project: dict, file: dict, layer_in_file: Optional[str] = None):
        super().__init__(project, file)
        self.layer_in_file = layer_in_file

    pass


class VectorStyleBuilderOld(StyleBuilder):
    """Collects style files for all layers in a vector file."""

    def validate_layers(self) -> bool:
        if not self.layers:
            self.failed.emit(
                f"No layers found for {self.file_ref_str}. Open the file in QGIS and try again."
            )
            return False
        return True

    def _create_qml_zip(self, zip_path: str):
        """Craete a QML zip file for all the qml files in the local directory"""
        try:
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for root, _, files in os.walk(self.tempdir):
                    for file in files:
                        if file.endswith(".qml"):
                            file_path = os.path.join(root, file)
                            zip_file.write(
                                file_path, os.path.relpath(file_path, self.tempdir)
                            )
        except Exception as e:
            self.failed.emit(f"Failed to create QML zip: {str(e)}")

    def save_qml_style_to_file(self) -> str:
        # Save QML style files for each layer to local directory
        for layer in self.layers:
            qml_path = os.path.join(self.tempdir, f"{layer.name()}.qml")
            layer.saveNamedStyle(str(qml_path))
        zip_path = os.path.join(self.tempdir, "qml.zip")
        self._create_qml_zip(zip_path)
        return zip_path

    def get_files(self) -> list:
        zip_path = self.save_qml_style_to_file()
        return [("files", "qml.zip", zip_path, "application/zip")]


class StyleUploader(QObject):
    """The StyleUploader takes care of uploading files generated by builder and is aware of the context"""

    # TODO: create StyleUploader for files using the file-descriptor based file path
    # TODO: create StyleUploader for publications using publication descriptor

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def upload_to_rana(self, files):
        raise NotImplementedError

    def connect_external_signals(self, signals, builder: StyleBuilder):
        builder.failed.connect(signals.failed.emit)
        self.failed.connect(signals.failed.emit)
        builder.warning.connect(signals.warning.emit)
        self.warning.connect(signals.warning.emit)

    def disconnect_external_signals(self, signals, builder: StyleBuilder):
        for signal, func in [
            (builder.failed, signals.failed.emit),
            (builder.warning, signals.warning.emit),
            (signals.failed, builder.failed.disconnect),
            (signals.warning, builder.warning.disconnect),
        ]:
            try:
                signal.disconnect(func)
            except TypeError:
                # TypeError is raised when signal is not connected
                continue

    @contextmanager
    def signal_connections(self, signals, builder: StyleBuilder):
        """Context manager to ensure signals are always connected and disconnected properly."""
        self.connect_external_signals(signals, builder)
        try:
            yield
        finally:
            self.disconnect_external_signals(signals, builder)

    def run(self, builder: StyleBuilder, signals):
        with self.signal_connections(signals, builder):
            # validate
            if not builder.validate_layers():
                return
            os.makedirs(builder.tempdir, exist_ok=True)
            # Collect files
            files = builder.get_files()
            # Upload styling files to rana
            self.upload_to_rana(files)
            # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
            try:
                shutil.rmtree(builder.tempdir)
            except (FileNotFoundError, PermissionError, OSError) as e:
                pass
            signals.finished.emit(
                f"Styling files uploaded successfully for {builder.file_ref_str}."
            )


class PublicationStyleUploader(StyleUploader):
    """Uploads style for a publication layer"""

    def __init__(
        self,
        project: dict,
        file: dict,
        publication_version: dict,
        layer_in_file: Optional[str],
    ):
        # TODO: supply builders instead of details
        local_file_path, _ = get_publication_layer_path(
            project["slug"], file["id"], layer_in_file
        )
        file_ref_str = f"file {file['id']} from {project['name']}"
        # TODO: catch errors - keep it silentish
        # Create builder based on data_type and fail if type is not supported or data is missing
        if file["data_type"] == "raster":
            builder = RasterStyleBuilder(local_file_path, file_ref_str)
        elif file["data_type"] == "vector":
            if layer_in_file:
                builder = VectorStyleBuilder(local_file_path, file_ref_str)
            else:
                raise ValueError(
                    "Cannot generate styling for vector file without layer reference"
                )
        else:
            raise ValueError(
                f"Cannot generate styling for file of type {file['data_type']}"
            )
        super().__init__(project, file, builder)
        self.publication_id = publication_version["publication_id"]
        self.publication_version = publication_version["version"]

    def upload_to_rana(self, files):
        upload_publication_style(self.publication_id, self.publication_version, files)


class RasterFileDescriptorStyleUploader(StyleUploader):
    """Uploads style for a single raster file to the old raster specific endpoint"""

    # TODO: once new endpoints are ready for use we can create a single FileDescriptorStyleUploader

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


class StyleWorkerSignals(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)


class SingleStyleUploadWorker(QThread):
    """Handles processing of style tasks using workers."""

    def __init__(self, uploader: StyleUploader, builder: StyleBuilder, communication):
        super().__init__()
        self.communication = communication
        self.uploader = uploader
        self.builder = builder
        self.signals = StyleWorkerSignals()
        # Connect signals from uploader and builder
        self.uploader.failed.connect(self.signals.failed.emit)
        self.uploader.warning.connect(self.signals.warning.emit)
        self.builder.failed.connect(self.signals.failed.emit)
        self.builder.warning.connect(self.signals.warning.emit)

    def run(self):
        # validate
        if not self.builder.validate_layers():
            return
        os.makedirs(self.builder.tempdir, exist_ok=True)
        # Collect files
        files = self.builder.get_files()
        # Upload styling files to rana
        self.uploader.upload_to_rana(files)
        # Clean up - don't worry too much about errors because tempdir will be cleaned on reboot anyway
        try:
            shutil.rmtree(self.builder.tempdir)
        except (FileNotFoundError, PermissionError, OSError) as e:
            pass
        self.signals.finished.emit(
            f"Styling files uploaded successfully for {self.builder.file_ref_str}."
        )


class BatchStyleUploadWorker(QThread):
    """Handles processing of style tasks using workers."""

    def __init__(self, uploader, communication):
        super().__init__()
        self.communication = communication
        self.uploader = uploader
        self.signals = StyleWorkerSignals()
