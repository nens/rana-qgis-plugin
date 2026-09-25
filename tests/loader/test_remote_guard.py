from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from qgis.core import QgsProject, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    set_rana_refs,
)
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.api import RanaFetchError
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)


@pytest.fixture
def loader(qgis_application):
    QgsProject.instance().clear()
    instance = Loader(MagicMock())
    yield instance
    QgsProject.instance().clear()


def linked_layer():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "roads", "memory")
    set_rana_refs(layer, RanaLayerRef("project", "folder/roads.gpkg", "descriptor"))
    QgsProject.instance().addMapLayer(layer)
    return layer


def style_item():
    return StyleUploadItem(
        data_type=DataType.vector,
        local_file_path="/tmp/roads.gpkg",
        file_ref_str="file folder/roads.gpkg",
        upload_func=MagicMock(),
        project_id="project",
        descriptor_id="descriptor",
    )


def data_item():
    return UploadableLayerItem(
        RanaLayerRef("project", "folder/roads.gpkg", "descriptor"),
        Path("/tmp/roads.gpkg"),
        "roads",
        "project",
    )


def test_missing_data_target_clears_refs_and_warns_with_filename(loader):
    layer = linked_layer()
    error = RanaFetchError("missing", "url", {}, status_code=404)

    with patch("rana_qgis_plugin.loader.get_tenant_project_file", side_effect=error):
        assert not loader.verify_data_target(data_item(), [layer])

    assert get_rana_refs(layer) is None
    loader.communication.bar_warn.assert_called_once()
    assert "roads.gpkg" in loader.communication.bar_warn.call_args.args[0]


def test_transient_style_target_keeps_refs(loader):
    layer = linked_layer()
    error = RanaFetchError("unavailable", "url", {}, status_code=503)

    with patch("rana_qgis_plugin.loader.get_tenant_file_descriptor", side_effect=error):
        assert not loader.verify_style_target(style_item(), [layer])

    assert get_rana_refs(layer) is not None
