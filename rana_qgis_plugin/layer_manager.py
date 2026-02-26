from pathlib import Path
from typing import Optional

from qgis.core import (
    QgsDataSourceUri,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import (
    QBuffer,
    QByteArray,
    QIODevice,
    QObject,
    QSettings,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtGui import QFont, QFontMetrics, QImage, QStandardItem

from rana_qgis_plugin.auth import get_authcfg_id
from rana_qgis_plugin.simulation.utils import load_remote_schematisation
from rana_qgis_plugin.utils import get_threedi_api
from rana_qgis_plugin.utils_api import get_tenant_file_descriptor
from rana_qgis_plugin.utils_qgis import get_threedi_results_analysis_tool_instance
from rana_qgis_plugin.utils_settings import hcc_working_dir

STYLE_DIR = Path(__file__).parent / "styles"


class LayerManager(QObject):
    # NOTE: not really sure why this is a class, there is barely any state
    def __init__(self, communication, parent):
        super().__init__(parent)
        self.communication = communication
        self.project_inst = QgsProject.instance()
        self.root = self.project_inst.layerTreeRoot()

    def add_from_file(self, local_file_path: str, project_name: str, file: dict):
        self.communication.clear_message_bar()
        path = file["id"]
        parents = [project_name] + path.split("/")[:-1]
        # Save the last modified date of the downloaded file in QSettings
        last_modified_key = f"{project_name}/{path}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])
        if file.get("data_type") == "scenario":
            self._add_layer_from_scenario(local_file_path, file, parents=parents)
        elif file.get("data_type") == "raster":
            self._add_layer_from_raster_file(local_file_path, file, parents=parents)
        elif file.get("data_type") == "vector":
            self._add_layers_from_vector_file(local_file_path, file, parents=parents)

    def _add_layer_from_raster_file(
        self, local_file_path: str, file: dict, parents: list
    ):
        layer = self._add_layer(
            QgsRasterLayer,
            parents=parents,
            layer_args=[local_file_path, Path(file["id"]).name],
        )
        file_name = Path(file["id"]).name
        if layer:
            self.communication.bar_info(
                f"Added layer {file_name}"
                + (f" to group {'/'.join(parents)}." if parents else ".")
            )
        else:
            self.communication.show_warn(f"Failed to add layer {file_name}.")

    def _add_layers_from_vector_file(
        self, local_file_path: str, file: dict, parents: Optional[list] = None
    ):
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        file_name = Path(file["id"]).name
        if descriptor["meta"] is None:
            self.communication.show_warn(
                f"No metadata found for {file_name}, processing probably has not finished yet."
            )
            return
        layers = descriptor["meta"].get("layers", [])
        if not layers:
            self.communication.show_warn(f"No layers found in {file_name}.")
            return
        for file_layer in layers:
            layer = self._add_layer(
                QgsVectorLayer,
                layer_args=[local_file_path, file_layer["name"], "ogr"],
                parents=parents,
            )
            if layer:
                qml_path = Path(local_file_path).parent.joinpath(
                    f"{file_layer['name']}.qml"
                )
                if qml_path.exists():
                    layer.loadNamedStyle(str(qml_path))
                    layer.triggerRepaint()
            else:
                self.communication.show_error(
                    f"Failed to add {file_layer['name']} layer from: {file_name}"
                )
        self.communication.bar_info(
            f"Added layers from {file_name}"
            + (f" to group {'/'.join(parents)}." if parents else ".")
        )

    def _add_layer_from_scenario(
        self, local_file_path: str, file: dict, parents: Optional[list]
    ):
        # if zip file, do nothing, else try to load in results analysis
        if local_file_path.endswith(".zip"):
            return
        # NOTE: this seems to fully depend on proper loading in the results analysis tool
        # TODO: add to same group as results analysis
        # TODO: create group in results analysis at correct level
        ra_tool = get_threedi_results_analysis_tool_instance()
        # Check whether result and gridadmin exist in the target folder
        result_path = Path(local_file_path).joinpath("results_3di.nc")
        admin_path = Path(local_file_path).joinpath("gridadmin.h5")
        waterdepth_path = Path(local_file_path).joinpath("max_waterdepth.tif")
        file_name = Path(file["id"]).name
        if result_path.exists() and admin_path.exists():
            if hasattr(ra_tool, "load_result"):
                if self.communication.ask(
                    self.parent(),
                    "Rana",
                    "Do you want to add the results of this simulation to the current project so you can analyse them with Results Analysis?",
                ):
                    ra_tool.load_result(result_path, admin_path)
                    # TODO: move outside layer manager??
                    if not ra_tool.dockwidget.isVisible():
                        ra_tool.toggle_results_manager.run()  # also does some initialisation
                    if waterdepth_path.exists():
                        layer = self._add_layer(
                            QgsRasterLayer,
                            layer_args=[
                                str(waterdepth_path),
                                "max_waterdepth.tif",
                                "gdal",
                            ],
                            parents=parents,
                        )
                        if layer:
                            # we only download non-temporal rasters, so always pick the first band
                            layer.loadNamedStyle(str(STYLE_DIR / "water_depth.qml"))
                            if hasattr(layer.renderer(), "setBand"):
                                layer.renderer().setBand(1)
                            self.communication.bar_info(
                                f"Added water depth layer for {file_name}"
                                + (
                                    f" to group {'/'.join(parents)}."
                                    if parents
                                    else "."
                                )
                            )
            else:
                self.communication.show_warn(
                    "Cannot add results as layer without Rana Results Analysis plugin"
                )

    def _add_layer(
        self, layer_class, parents: Optional[list], layer_args: list
    ) -> Optional[QgsMapLayer]:
        layer = layer_class(*layer_args)
        if layer.isValid():
            self.project_inst.addMapLayer(layer, False)
            root = self.root
            if parents:
                for parent in parents:
                    if not root.findGroup(parent):
                        root = root.addGroup(parent)
                    else:
                        root = root.findGroup(parent)
            root.addLayer(layer)
            return layer

    def add_from_wms(self, project_name: str, file: dict):
        # TODO: add to same group as results analysis
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        parents = [project_name] + file["id"].split("/")
        file_name = Path(file["id"]).name
        for link in descriptor["links"]:
            if link["rel"] == "wms":
                for layer in descriptor["meta"]["layers"]:
                    quri = QgsDataSourceUri()
                    quri.setParam("layers", layer["code"])
                    quri.setParam("styles", "")
                    quri.setParam("format", "image/png")
                    quri.setParam("url", link["href"])
                    # the wms provider will take care to expand authcfg URI parameter with credential
                    # just before setting the HTTP connection.
                    quri.setAuthConfigId(get_authcfg_id())
                    self._add_layer(
                        QgsRasterLayer,
                        parents=parents,
                        layer_args=[
                            bytes(quri.encodedUri()).decode(),
                            f"{layer['name']} ({layer['label']})",
                            "wms",
                        ],
                    )
                self.communication.bar_info(
                    f"Added layers from {file_name} to group {'/'.join(parents)}."
                )
                return
        self.communication.show_error(f"Cannot add wms layer(s) from {file_name}")

    def add_from_schematisation(self, schematisation_instance):
        self.communication.clear_message_bar()
        # TODO: handle other revisions
        schematisation = schematisation_instance["schematisation"]
        revision = schematisation_instance["latest_revision"]
        if not revision:
            self.communication.show_warn(
                "Cannot open a schematisation without a revision."
            )
            return
        pb = self.communication.progress_bar(
            msg="Downloading remote schematisation...", clear_msg_bar=True
        )
        if not hcc_working_dir():
            self.communication.show_warn(
                "Working directory not yet set, please configure this in the plugin settings."
            )
            return
        load_remote_schematisation(
            self.communication,
            schematisation,
            revision,
            pb,
            hcc_working_dir(),
            get_threedi_api(),
        )
        self.communication.clear_message_bar()
