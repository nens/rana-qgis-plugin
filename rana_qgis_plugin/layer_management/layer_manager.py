from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar, Optional, cast

from qgis._core import QgsMapLayer
from qgis.core import (
    QgsDataSourceUri,
    QgsLayerTreeGroup,
    QgsLayerTreeLayer,
    QgsMapLayer,
    QgsProject,
    QgsRasterLayer,
    QgsVectorLayer,
)
from qgis.PyQt.QtCore import (
    QObject,
    QSettings,
)

from rana_qgis_plugin.layer_management.dirty_tracking import attach_dirty_tracking
from rana_qgis_plugin.legacy.auth import get_authcfg_id
from rana_qgis_plugin.legacy.simulation.utils import (
    BuildOptionActions,
    load_local_schematisation,
)
from rana_qgis_plugin.utils.api import (
    get_tenant_file_descriptor,
)
from rana_qgis_plugin.utils.qgis import (
    get_qml_name_for_layer,
    get_threedi_results_analysis_tool_instance,
)
from rana_qgis_plugin.utils.scenario import get_is_3di_simulation


class LayerManager(QObject):
    # NOTE: not really sure why this is a class, there is barely any state
    def __init__(self, communication, parent):
        super().__init__(parent)
        self.communication = communication
        self.project_inst = QgsProject.instance()
        assert self.project_inst is not None
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
        file_name = Path(file["id"]).name
        layer = self._create_and_add_layer(
            QgsRasterLayer,
            parents=parents,
            layer_args=[local_file_path, display_name or file_name],
        )
        if layer:
            self._unlock_layer(layer)
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
        parents = (parents or []) + [file_name]
        if descriptor is None or not isinstance(descriptor.get("meta"), dict):
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
            qml_path = Path(local_file_path).parent.joinpath(
                get_qml_name_for_layer(layer_name)
            )
            if qml_path.exists():
                layer.loadNamedStyle(str(qml_path))
                layer.triggerRepaint()
            self._unlock_layer(layer)
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
            else:
                self.communication.show_warn(
                    "Cannot add results as layer without Rana Results Analysis plugin"
                )

    def add_layer(self, layer, parents: Optional[list[str]] = None):
        root = cast(QgsLayerTreeGroup, self.root)
        if parents:
            for parent in parents:
                existing_group = root.findGroup(parent)
                if existing_group is None:
                    new_group = root.addGroup(parent)
                    if new_group is None:
                        raise RuntimeError(
                            f"Unable to create layer tree group: {parent}"
                        )
                    root = new_group
                else:
                    root = existing_group
        # Check if layer with same name and source already exists in root
        child_layers = []
        for child in root.children():
            if isinstance(child, QgsLayerTreeLayer):
                child_layer = child.layer()
                if child_layer is not None:
                    child_layers.append(child_layer)
        existing_layer = next(
            (
                child_layer
                for child_layer in child_layers
                if child_layer.name() == layer.name()
                and child_layer.source() == layer.source()
            ),
            None,
        )
        insert_index = len(root.children())
        # If the layer already exists, remove it first and then replace with the current layer
        if existing_layer:
            # Get the index of the existing layer before removing it
            existing_node = root.findLayer(existing_layer.id())
            if existing_node:
                node_parent = existing_node.parent()
                if node_parent is None:
                    raise RuntimeError("Existing layer tree node has no parent")
                insert_index = node_parent.children().index(existing_node)
            project = self.project_inst
            assert project is not None
            project.removeMapLayer(existing_layer.id())
        project = self.project_inst
        assert project is not None
        project.addMapLayer(layer, False)
        root.insertLayer(insert_index, layer)

    def _create_and_add_layer(
        self, layer_class: Any, parents: Optional[list[str]], layer_args: list
    ) -> Optional[QgsMapLayer]:
        layer = layer_class(*layer_args)
        if layer.isValid():
            self.add_layer(layer, parents)
            return layer
        return None

    def _unlock_layer(self, layer):
        # Add the 'Removable' flag explicitly to prevent settings in the source from locking the layer'
        current_flags = layer.flags()
        new_flags = current_flags | QgsMapLayer.LayerFlag.Removable
        layer.setFlags(new_flags)

    def _add_wms_for_layer(self, layer, link, parents):
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

    def _add_from_wms(self, file: dict, layers: list, parents: list[str]):
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if descriptor is None or not isinstance(descriptor.get("links"), list):
            self.communication.show_error(
                f"Cannot add wms layer(s) from {Path(file['id']).name}"
            )
            return
        wms_link = next(
            (link for link in descriptor["links"] if link["rel"] == "wms"), None
        )
        if wms_link:
            if len(layers) == 0:
                self.communication.bar_info("No layers present in this file.")
                return
            for layer in layers:
                self._add_wms_for_layer(layer, wms_link, parents=parents)
            self.communication.bar_info(
                f"Added layers from {Path(file['id']).name} to group {'/'.join(parents)}."
            )
        else:
            self.communication.show_error(
                f"Cannot add wms layer(s) from {Path(file['id']).name}"
            )

    def add_from_schematisation(
        self,
        project_name,
        local_schematisation,
        revision_number,
        wip_replace_requested,
        geopackage_filepath=None,
    ):
        """Open a previously downloaded schematisation in the schematisation editor."""
        self.communication.clear_message_bar()
        if not local_schematisation:
            self.communication.log_warn("Unable to load local schematisation")
            return

        assert revision_number in local_schematisation.revisions
        load_local_schematisation(
            self.communication,
            local_schematisation=local_schematisation.wip_revision
            if wip_replace_requested
            else local_schematisation.revisions[revision_number],
            action=BuildOptionActions.DOWNLOADED,
            custom_geopackage_filepath=geopackage_filepath,
            parents=[project_name],
        )
        wip_revision = local_schematisation.wip_revision
        if wip_revision is not None:
            settings = QSettings("3di", "qgisplugin")
            settings.setValue(
                "last_used_geopackage_path", wip_revision.schematisation_dir
            )


class FileLayerManager(LayerManager):
    def add_from_wms(self, project_name, file: dict):
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        parents = [project_name] + file["id"].split("/")
        if descriptor is not None and isinstance(descriptor.get("meta"), dict):
            super()._add_from_wms(
                file, descriptor["meta"].get("layers", []), parents=parents
            )

    def add_from_file(self, project_name, local_file_path: str, file: dict):
        self.communication.clear_message_bar()
        parents = [project_name] + file["id"].split("/")[:-1]
        # Save the last modified date of the downloaded file in QSettings
        last_modified_key = f"{project_name}/{file['id']}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])
        if file.get("data_type") == "scenario":
            descriptor = get_tenant_file_descriptor(file["descriptor_id"])
            if descriptor is not None and get_is_3di_simulation(descriptor):
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
        layer_in_file: Optional[str] = None,
    ):
        super().__init__(communication, parent)
        self.publication_tree = publication_tree
        self.display_name = display_name
        self.layer_in_file = layer_in_file

    def add_from_wms(self, project_name, file: dict):
        parents = [project_name, "publications"] + self.publication_tree
        descriptor = get_tenant_file_descriptor(file["descriptor_id"])
        if descriptor is None or not isinstance(descriptor.get("meta"), dict):
            self.communication.show_error(f"Failed to add {self.display_name} from WMS")
            return
        # match layer_in_file to code to retrieve the full layer data
        layer = next(
            (
                layer
                for layer in descriptor["meta"]["layers"]
                if layer["code"] == self.layer_in_file
            ),
            None,
        )
        if layer:
            super()._add_from_wms(file, [layer], parents=parents)
        else:
            self.communication.show_error(f"Failed to add {self.display_name} from WMS")

    def add_from_file(self, project_name, local_file_path: str, file: dict):
        # Save the last modified date of the downloaded file in QSettings
        parents = [project_name, "publications"] + self.publication_tree
        last_modified_key = f"{project_name}/{file['id']}/last_modified"
        QSettings().setValue(last_modified_key, file["last_modified"])
        if file.get("data_type") == "scenario" and self.layer_in_file:
            self.add_from_wms(project_name, file)
        elif file.get("data_type") == "raster":
            self._add_layer_from_raster_file(
                local_file_path, file, parents=parents, display_name=self.display_name
            )
        elif file.get("data_type") == "vector" and self.layer_in_file:
            self._add_layers_from_vector_file(
                self.layer_in_file, local_file_path, file, parents=parents
            )


def open_file_via_layer_manager(
    project: dict, file: dict, local_file_path: str, layer_manager: LayerManager
):
    if file["data_type"] in ["scenario", "vector", "raster"]:
        layer_manager.add_from_file(project["name"], local_file_path, file)


# ---------------------------------------------------------------------------
# New module-level functions for Rana data-item-driven layer opening.
# The legacy LayerManager classes above remain as reference until all
# functionality (WMS, scenario, schematisation, publications) is ported.
# ---------------------------------------------------------------------------

_GROUP_PROJECT_ID_KEY = "rana/project_id"
_GROUP_PATH_SEGMENT_KEY = "rana/path_segment"


@dataclass(frozen=True)
class RanaLayerRef:
    """Identify the Rana resource represented by a map layer."""

    project_id: str
    file_id: str
    descriptor_id: Optional[str] = None
    layer_id: Optional[str] = None

    PROPERTY_KEYS: ClassVar[dict[str, str]] = {
        "project_id": "rana/project_id",
        "file_id": "rana/file_id",
        "descriptor_id": "rana/descriptor_id",
        "layer_id": "rana/layer_id",
    }

    @staticmethod
    def from_layer(layer: QgsMapLayer) -> Optional["RanaLayerRef"]:
        """Create a reference from a layer's Rana custom properties."""
        values = {
            field: layer.customProperty(property_key)
            for field, property_key in RanaLayerRef.PROPERTY_KEYS.items()
        }
        project_id = values.get("project_id")
        file_id = values.get("file_id")
        if not isinstance(project_id, str) or not isinstance(file_id, str):
            return None
        values.update(project_id=project_id, file_id=file_id)
        return RanaLayerRef(
            project_id=project_id,
            file_id=file_id,
            **{
                key: values.get(key)
                for key in RanaLayerRef.PROPERTY_KEYS
                if key not in {"project_id", "file_id"}
            },
        )

    def apply_to(self, layer: QgsMapLayer) -> None:
        """Store this reference in the layer's Rana custom properties."""
        for field, property_key in self.PROPERTY_KEYS.items():
            layer.setCustomProperty(property_key, getattr(self, field))


def set_rana_refs(layer: QgsMapLayer, rana_refs: RanaLayerRef) -> None:
    """Store a Rana reference in a map layer."""
    rana_refs.apply_to(layer)


def get_rana_refs(layer: QgsMapLayer) -> Optional[RanaLayerRef]:
    """Return the stored Rana reference, or None for an unlinked layer."""
    return RanaLayerRef.from_layer(layer)


def clear_rana_refs(layer: QgsMapLayer) -> None:
    """Remove the stored Rana reference from a map layer."""
    for property_key in RanaLayerRef.PROPERTY_KEYS.values():
        layer.removeCustomProperty(property_key)


def is_rana_linked(layer: QgsMapLayer) -> bool:
    """Return whether a map layer has a complete Rana reference."""
    return get_rana_refs(layer) is not None


def find_or_create_rana_group(
    parent: QgsLayerTreeGroup, segment: str, project_id: str
) -> QgsLayerTreeGroup:
    """Find an existing child group matching Rana metadata, or create one."""
    for child in parent.children():
        if (
            isinstance(child, QgsLayerTreeGroup)
            and child.customProperty(_GROUP_PROJECT_ID_KEY) == project_id
            and child.customProperty(_GROUP_PATH_SEGMENT_KEY) == segment
        ):
            return child
    group = parent.addGroup(segment)
    assert group is not None
    group.setCustomProperty(_GROUP_PROJECT_ID_KEY, project_id)
    group.setCustomProperty(_GROUP_PATH_SEGMENT_KEY, segment)
    return group


def find_or_create_rana_groups(
    parents: list[str], project_id: str
) -> QgsLayerTreeGroup:
    """Walk *parents* segments, creating Rana-tagged groups as needed."""
    project = QgsProject.instance()
    assert project is not None
    root = project.layerTreeRoot()
    assert root is not None
    current: QgsLayerTreeGroup = root
    for segment in parents:
        current = find_or_create_rana_group(current, segment, project_id)
    return current


def add_layer_to_group(layer: QgsMapLayer, group: QgsLayerTreeGroup) -> None:
    """Add *layer* to *group*, replacing an existing layer with the same source."""
    project = QgsProject.instance()
    assert project is not None

    existing_layers = []
    for child in group.children():
        if isinstance(child, QgsLayerTreeLayer):
            child_layer = child.layer()
            if child_layer is not None:
                existing_layers.append(child_layer)
    insert_index = len(group.children())
    for existing in existing_layers:
        if existing.name() == layer.name() and existing.source() == layer.source():
            node = group.findLayer(existing.id())
            if node:
                parent = node.parent()
                assert parent is not None
                insert_index = parent.children().index(node)
            project.removeMapLayer(existing.id())
            break

    project.addMapLayer(layer, False)
    group.insertLayer(insert_index, layer)
    layer.setFlags(layer.flags() | QgsMapLayer.LayerFlag.Removable)


def open_rana_raster(
    local_file_path: str,
    parents: list[str],
    ref: RanaLayerRef,
) -> Optional[QgsRasterLayer]:
    """Open a Rana raster file into the layer panel."""
    display_name = Path(local_file_path).name
    layer = QgsRasterLayer(local_file_path, display_name)
    if not layer.isValid():
        return None
    group = find_or_create_rana_groups(parents, ref.project_id)
    set_rana_refs(layer, ref)
    qml_path = Path(local_file_path).parent / get_qml_name_for_layer(display_name)
    if qml_path.exists():
        layer.loadNamedStyle(str(qml_path))
    attach_dirty_tracking(layer)
    add_layer_to_group(layer, group)
    return layer


def open_rana_vector_layer(
    local_file_path: str,
    layer_name: str,
    parents: list[str],
    ref: RanaLayerRef,
) -> Optional[QgsVectorLayer]:
    """Open a single vector layer into the layer panel."""
    layer_uri = f"{local_file_path}|layername={layer_name}"
    layer = QgsVectorLayer(layer_uri, layer_name, "ogr")
    if not layer.isValid():
        return None
    group = find_or_create_rana_groups(parents, ref.project_id)
    set_rana_refs(layer, ref)
    qml_path = Path(local_file_path).parent / get_qml_name_for_layer(layer_name)
    if qml_path.exists():
        layer.loadNamedStyle(str(qml_path))
    attach_dirty_tracking(layer)
    add_layer_to_group(layer, group)
    return layer


def open_rana_vector_layers(
    local_file_path: str,
    layer_names: list[str],
    parents: list[str],
    ref: RanaLayerRef,
) -> list[QgsVectorLayer]:
    """Open all named layers from a vector file into the layer panel."""
    layers = []
    for name in layer_names:
        layer = open_rana_vector_layer(local_file_path, name, parents, ref)
        if layer is not None:
            layers.append(layer)
    return layers


def get_vector_layer_names(local_file_path: str) -> list[str]:
    """Discover vector layer names from a file on disk using OGR."""
    from osgeo import ogr

    ds = ogr.Open(local_file_path)
    if ds is None:
        return []
    names = [ds.GetLayerByIndex(i).GetName() for i in range(ds.GetLayerCount())]
    ds = None
    return names
