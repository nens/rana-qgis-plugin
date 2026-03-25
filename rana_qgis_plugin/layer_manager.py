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
from rana_qgis_plugin.utils_api import (
    get_tenant_file_descriptor,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utils_qgis import get_threedi_results_analysis_tool_instance
from rana_qgis_plugin.utils_scenario import get_is_3di_simulation
from rana_qgis_plugin.utils_settings import hcc_working_dir

STYLE_DIR = Path(__file__).parent / "styles"


class LayerManager(QObject):
    # NOTE: not really sure why this is a class, there is barely any state
    def __init__(self, communication, parent):
        super().__init__(parent)
        self.communication = communication
        self.project_inst = QgsProject.instance()
        self.root = self.project_inst.layerTreeRoot()

    def add_from_file(self, project_name, local_file_path: str, file: dict):
        raise NotImplementedError

    def _add_layer_from_raster_file(
        self,
        local_file_path: str,
        file: dict,
        parents: list,
        display_name: Optional[str] = None,
    ):
        layer = self._create_and_add_layer(
            QgsRasterLayer,
            parents=parents,
            layer_args=[local_file_path, display_name or Path(file["id"]).name],
        )
        file_name = Path(file["id"]).name
        if layer:
            self.communication.bar_info(
                f"Added layer {file_name}"
                + (f" to group {'/'.join(parents)}." if parents else ".")
            )
        else:
            self.communication.show_warn(f"Failed to add layer {file_name}.")

    def _add_all_layers_from_vector_file(
        self, local_file_path: str, file: dict, parents: Optional[list[str]] = None
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
            self._add_layers_from_vector_file(
                file_layer["name"], local_file_path, file, parents=parents
            )
        self.communication.bar_info(
            f"Added layers from {file_name}"
            + (f" to group {'/'.join(parents)}." if parents else ".")
        )

    def _add_layers_from_vector_file(
        self,
        layer_name,
        local_file_path: str,
        file: dict,
        parents: Optional[list[str]] = None,
    ):
        layer_uri = f"{local_file_path}|layername={layer_name}"
        layer = self._create_and_add_layer(
            QgsVectorLayer,
            layer_args=[layer_uri, layer_name, "ogr"],
            parents=parents,
        )
        if layer:
            qml_path = Path(local_file_path).parent.joinpath(f"{layer_name}.qml")
            if qml_path.exists():
                layer.loadNamedStyle(str(qml_path))
                layer.triggerRepaint()
        else:
            self.communication.show_error(
                f"Failed to add {layer_name} layer from: {Path(file['id']).name}"
            )

    def _add_layer_from_scenario(self, local_file_path: str, file: dict, project: str):
        # if zip file, do nothing, else try to load in results analysis
        if local_file_path.endswith(".zip"):
            return
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
                    try:
                        ra_tool.load_result(result_path, admin_path, project=project)
                    except TypeError as e:
                        if "project" in str(e):
                            # Warn and fall back on old syntax and behavior
                            self.communication.show_warn(
                                "Rana results analysis is not up to date and therefore the results layers will not be organized by project. Please update the plugin."
                            )
                            ra_tool.load_result(result_path, admin_path)
                        else:
                            raise
                    if not ra_tool.dockwidget.isVisible():
                        ra_tool.toggle_results_manager.run()  # also does some initialisation
                    if waterdepth_path.exists():
                        # construct waterdepth parents based on metadata
                        waterdepth_parents = [project]
                        file_descriptor = get_tenant_file_descriptor(
                            file["descriptor_id"]
                        )
                        if file_descriptor and file_descriptor.get("meta"):
                            meta = file_descriptor["meta"]
                            rev_name = meta.get("schematisation", {}).get("name")
                            if rev_name:
                                waterdepth_parents.append(rev_name)
                            waterdepth_parents.append("Waterdepth")
                            sim_name = meta.get("simulation", {}).get("name")
                            if sim_name:
                                waterdepth_parents.append(sim_name)
                        layer = self._create_and_add_layer(
                            QgsRasterLayer,
                            layer_args=[
                                str(waterdepth_path),
                                "max_waterdepth.tif",
                                "gdal",
                            ],
                            parents=waterdepth_parents,
                        )
                        if layer:
                            # we only download non-temporal rasters, so always pick the first band
                            layer.loadNamedStyle(str(STYLE_DIR / "water_depth.qml"))
                            if hasattr(layer.renderer(), "setBand"):
                                layer.renderer().setBand(1)
                            self.communication.bar_info(
                                f"Added water depth layer for {file_name}"
                                + (
                                    f" to group {'/'.join(waterdepth_parents)}."
                                    if waterdepth_parents
                                    else "."
                                )
                            )
            else:
                self.communication.show_warn(
                    "Cannot add results as layer without Rana Results Analysis plugin"
                )

    def add_layer(self, layer, parents: Optional[list[str]] = None):
        self.project_inst.addMapLayer(layer, False)
        root = self.root
        if parents:
            for parent in parents:
                if not root.findGroup(parent):
                    root = root.addGroup(parent)
                else:
                    root = root.findGroup(parent)
        root.addLayer(layer)

    def _create_and_add_layer(
        self, layer_class, parents: Optional[list[str]], layer_args: list
    ) -> Optional[QgsMapLayer]:
        layer = layer_class(*layer_args)
        if layer.isValid():
            self.add_layer(layer, parents)
            return layer

    def add_from_wms(self, project_name, file: dict):
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
                    self._create_and_add_layer(
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

    def add_from_schematisation(self, project_name, schematisation, revision):
        self.communication.clear_message_bar()
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
            parents=[project_name],
        )
        self.communication.clear_message_bar()


class FileLayerManager(LayerManager):
    def add_from_file(self, project_name, local_file_path: str, file: dict):
        self.communication.clear_message_bar()
        parents = [project_name] + file["id"].split("/")[:-1]
        # Save the last modified date of the downloaded file in QSettings
        last_modified_key = f"{project_name}/{file['id']}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])
        if file.get("data_type") == "scenario":
            descriptor = get_tenant_file_descriptor(file["descriptor_id"])
            if get_is_3di_simulation(descriptor):
                self._add_layer_from_scenario(
                    local_file_path, file, project=project_name
                )
        elif file.get("data_type") == "raster":
            self._add_layer_from_raster_file(local_file_path, file, parents=parents)
        elif file.get("data_type") == "vector":
            self._add_all_layers_from_vector_file(
                local_file_path, file, parents=parents
            )


class PublicationLayerManager(LayerManager):
    def __init__(
        self,
        communication,
        parent,
        publication_tree: list[str],
        display_name: str,
        layer_name_in_file: Optional[str] = None,
    ):
        super().__init__(communication, parent)
        self.publication_tree = publication_tree
        self.display_name = display_name
        self.layer_name = layer_name_in_file

    def add_from_file(self, project_name, local_file_path: str, file: dict):
        # Save the last modified date of the downloaded file in QSettings
        parents = [project_name, "publications"] + self.publication_tree
        last_modified_key = f"{project_name}/{file['id']}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])
        if file.get("data_type") == "scenario":
            pass
            # TODO: handle scenario
            # descriptor = get_tenant_file_descriptor(file["descriptor_id"])
            # if get_is_3di_simulation(descriptor):
            #     self._add_layer_from_scenario(
            #         local_file_path, file, project=project_name
            #     )
        elif file.get("data_type") == "raster":
            self._add_layer_from_raster_file(
                local_file_path, file, parents=parents, display_name=self.display_name
            )
        elif file.get("data_type") == "vector" and self.layer_name:
            self._add_layers_from_vector_file(
                self.layer_name, local_file_path, file, parents=parents
            )
            # self._add_layers_from_vector_file(local_file_path, file, parents=parents)


def open_file_via_layer_manager(
    project: dict, file: dict, local_file_path: str, layer_manager: LayerManager
):
    if file["data_type"] == "threedi_schematisation":
        schematisation = get_threedi_schematisation(
            layer_manager.communication, file["descriptor_id"]
        )
        if schematisation:
            revision = schematisation["latest_revision"]
            if not revision:
                layer_manager.communication.show_warn(
                    "Cannot open a schematisation without a revision."
                )
                return
            layer_manager.add_from_schematisation(
                project["name"], schematisation["schematisation"], revision
            )
    elif file["data_type"] in ["scenario", "vector", "raster"]:
        layer_manager.add_from_file(project["name"], local_file_path, file)
