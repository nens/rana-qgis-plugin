from dataclasses import replace

import pytest
from qgis.core import QgsProject, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    is_rana_linked,
    set_rana_refs,
)
from rana_qgis_plugin.layer_management.local_linking import LocalLinkingListener

REF = RanaLayerRef(
    project_id="proj-1",
    file_id="folder/sub/data.gpkg",
    descriptor_id="desc-1",
)


@pytest.fixture(autouse=True)
def clean_project(qgis_application):
    QgsProject.instance().clear()
    yield
    QgsProject.instance().clear()


def _add_linked_layer(ref: RanaLayerRef) -> QgsVectorLayer:
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")
    set_rana_refs(layer, ref)
    QgsProject.instance().addMapLayer(layer)
    return layer


class TestOnItemRenamed:
    def test_file_rename_updates_ref(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_renamed(
            "folder/sub/data.gpkg", "folder/sub/renamed.gpkg", "proj-1", False
        )

        updated = get_rana_refs(layer)
        assert updated is not None
        assert updated.file_id == "folder/sub/renamed.gpkg"
        assert updated.descriptor_id == "desc-1"

    def test_folder_rename_remaps_prefix(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_renamed("folder/sub", "folder/other", "proj-1", True)

        updated = get_rana_refs(layer)
        assert updated is not None
        assert updated.file_id == "folder/other/data.gpkg"

    def test_unrelated_rename_is_ignored(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_renamed(
            "unrelated/file.gpkg", "unrelated/new.gpkg", "proj-1", False
        )

        assert get_rana_refs(layer) == REF


class TestOnItemDeleted:
    def test_file_delete_clears_refs(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_deleted("folder/sub/data.gpkg", "proj-1", False)

        assert not is_rana_linked(layer)

    def test_folder_delete_clears_children(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_deleted("folder/sub", "proj-1", True)

        assert not is_rana_linked(layer)

    def test_unrelated_delete_is_ignored(self):
        layer = _add_linked_layer(REF)
        listener = LocalLinkingListener.__new__(LocalLinkingListener)

        listener.on_item_deleted("other/file.gpkg", "proj-1", False)

        assert is_rana_linked(layer)


def test_rename_does_not_cross_projects():
    first = _add_linked_layer(REF)
    second = _add_linked_layer(replace(REF, project_id="proj-2"))
    listener = LocalLinkingListener.__new__(LocalLinkingListener)

    listener.on_item_renamed(
        "folder/sub/data.gpkg", "folder/sub/renamed.gpkg", "proj-1", False
    )

    assert get_rana_refs(first).file_id == "folder/sub/renamed.gpkg"
    assert get_rana_refs(second) == replace(REF, project_id="proj-2")


def test_delete_does_not_cross_projects():
    first = _add_linked_layer(REF)
    second = _add_linked_layer(replace(REF, project_id="proj-2"))
    listener = LocalLinkingListener.__new__(LocalLinkingListener)

    listener.on_item_deleted("folder/sub/data.gpkg", "proj-1", False)

    assert not is_rana_linked(first)
    assert is_rana_linked(second)
