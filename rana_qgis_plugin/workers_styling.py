import copy
import json
import math
import os
import zipfile
from functools import cached_property
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

from rana_qgis_plugin.utils import get_local_file_path, image_to_bytes
from rana_qgis_plugin.utils_api import (
    get_vector_style_upload_urls,
    upload_raster_styling,
)
from rana_qgis_plugin.utils_lizard import import_from_geostyler


class StyleBuilder(QObject):
    """Style builder takes care of collecting style files; it is unaware of any context"""

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(self, project: dict, file: dict):
        super().__init__()
        self.project = project
        self.file = file

    @property
    def filename(self):
        return os.path.basename(self.file["id"].rstrip("/"))

    @cached_property
    def layers(self):
        all_layers = QgsProject.instance().mapLayers().values()
        return [layer for layer in all_layers if self.filename in layer.source()]

    def validate_layers(self) -> bool:
        raise NotImplementedError

    def save_qml_style_to_file(self, local_dir: str) -> str:
        raise NotImplementedError

    def get_files(self, local_dir: str) -> list:
        raise NotImplementedError


class RasterStyleBuilder(StyleBuilder):
    def validate_layers(self) -> bool:
        if not self.layers:
            self.failed.emit(
                f"No layers found for {self.filename}. Open the file in QGIS and try again."
            )
            return False
        elif not len(self.layers) == 1:
            self.failed.emit(
                f"Multiple layers found for {self.filename}. Open the file in QGIS and try again."
            )
            return False
        return True

    def save_qml_style_to_file(self, local_dir: str) -> str:
        layer = self.layers[0]
        qml_file_name = os.path.splitext(layer.name())[0] + ".qml"
        qml_path = os.path.join(local_dir, qml_file_name)
        layer.saveNamedStyle(str(qml_path))
        zip_path = os.path.join(local_dir, "qml.zip")
        with zipfile.ZipFile(zip_path, "w") as zipf:
            zipf.write(qml_path, qml_file_name)
        return zip_path

    def get_files(self, local_dir: str) -> list:
        zip_path = self.save_qml_style_to_file(local_dir)
        lizard_styling_path = self._save_lizard_style_to_file(local_dir)
        return [
            ("files", "colormap.json", lizard_styling_path, "application/json"),
            ("files", "qml.zip", zip_path, "application/zip"),
        ]

    def _save_lizard_style_to_file(self, local_dir: str):
        layer = self.layers[0]
        geostyler, _, _, warnings = togeostyler.convert(layer)
        if len(geostyler["rules"]) != 1:
            self.failed.emit(f"Multiple rules found for {self.filename}.")
            return
        if len(geostyler["rules"][0]["symbolizers"]) != 1:
            self.failed.emit(f"Multiple symbolizers found for {self.filename}.")
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
        lizard_styling_path = os.path.join(local_dir, "colormap.json")
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
                f"No layers found for {self.filename}. Open the file in QGIS and try again."
            )
            return False
        return True

    def _create_qml_zip(self, local_dir: str, zip_path: str):
        """Craete a QML zip file for all the qml files in the local directory"""
        try:
            with zipfile.ZipFile(zip_path, "w") as zip_file:
                for root, _, files in os.walk(local_dir):
                    for file in files:
                        if file.endswith(".qml"):
                            file_path = os.path.join(root, file)
                            zip_file.write(
                                file_path, os.path.relpath(file_path, local_dir)
                            )
        except Exception as e:
            self.failed.emit(f"Failed to create QML zip: {str(e)}")

    def save_qml_style_to_file(self, local_dir) -> str:
        # Save QML style files for each layer to local directory
        for layer in self.layers:
            qml_path = os.path.join(local_dir, f"{layer.name()}.qml")
            layer.saveNamedStyle(str(qml_path))
        zip_path = os.path.join(local_dir, "qml.zip")
        self._create_qml_zip(local_dir, zip_path)
        return zip_path

    def get_files(self, local_dir: str) -> list:
        zip_path = self.save_qml_style_to_file(local_dir)
        return [("files", "qml.zip", zip_path, "application/zip")]


class StyleWorkerSignals(QObject):
    finished = pyqtSignal(str)
    failed = pyqtSignal(str)
    warning = pyqtSignal(str)


class SingleStyleUploader(QThread):
    """Handles processing of style tasks using workers."""

    def __init__(self, uploader, communication):
        super().__init__()
        self.communication = communication
        self.uploader = uploader
        self.signals = StyleWorkerSignals()

    def run(self):
        self.uploader.run(self.signals)


class StyleUploader(QObject):
    """The StyleUploader takes care of uploading files generated by builder and is aware of the context"""

    # TODO: create StyleUploader for files using the file-descriptor based file path
    # TODO: create StyleUploader for publications using publication descriptor

    failed = pyqtSignal(str)
    warning = pyqtSignal(str)

    def __init__(
        self,
        project: dict,
        file: dict,
        builder: StyleBuilder,
    ):
        super().__init__()
        self.project = project
        self.file = file
        self.builder = builder

    def upload_to_rana(self, files):
        raise NotImplementedError

    @property
    def local_dir(self):
        # TODO: make this temp!
        local_dir, _ = get_local_file_path(self.project["slug"], self.file["id"])
        return local_dir

    def run(self, signals):
        # connect signals
        self.builder.failed.connect(signals.failed.emit)
        self.failed.connect(signals.failed.emit)
        self.builder.warning.connect(signals.warning.emit)
        self.warning.connect(signals.warning.emit)
        # validate
        if not self.builder.validate_layers():
            return
        os.makedirs(self.local_dir, exist_ok=True)
        # Collect files
        files = self.builder.get_files(self.local_dir)
        # Upload styling files to rana
        self.upload_to_rana(files)
        # Clean up
        for item in files:
            # TODO: handle filesystem issue?
            # TODO: use a nicer file structure
            os.remove(item[2])
        signals.finished.emit(
            f"Styling files uploaded successfully for {self.builder.filename}."
        )


class RasterFileStyleUploader(StyleUploader):
    """Uploads style for a single raster file to the old raster specific endpoint"""

    def __init__(
        self,
        project: dict,
        file: dict,
    ):
        super().__init__(project, file, RasterStyleBuilder(project, file))

    def upload_to_rana(self, files):
        try:
            upload_raster_styling(self.file["descriptor_id"], files)
        except Exception as e:
            self.failed.emit(f"Uploading styling files failed: {e}")


class PublicationStyleUploader(StyleUploader):
    """Uploads style for a publication layer"""

    def __init__(self, project: dict, file: dict, layer_in_file: Optional[str]):
        if file["data_type"] == "raster":
            builder = RasterStyleBuilder(project, file)
        elif file["data_type"] == "vector":
            builder = VectorStyleBuilder(project, file, layer_in_file)
        super().__init__(project, file, builder)


class VectorFileStyleUploaderOld(StyleUploader):
    """Uploads style for all layers in a vector file to the old vector specific"""

    def __init__(
        self,
        project: dict,
        file: dict,
    ):
        super().__init__(project, file, VectorStyleBuilderOld(project, file))

    def upload_to_rana(self, files):
        descriptor_id = self.file["descriptor_id"]
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
            upload_urls = get_vector_style_upload_urls(descriptor_id)

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
