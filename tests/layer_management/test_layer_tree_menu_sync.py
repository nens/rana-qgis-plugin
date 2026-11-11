from pathlib import Path

import pytest
from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.layer_management import layer_tree_menu
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.layer_management.sync_changes import (
    SyncChanges,
    SyncKind,
    file_key,
)
from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)


class FakeInterface:
    def mainWindow(self):
        return None


class FakeLoader:
    def __init__(self):
        self.data_items = None
        self.style_items = None

    def upload_existing_files(self, items):
        self.data_items = items

    def upload_styles(self, items):
        self.style_items = items


class FakeSyncDialog:
    def __init__(self, *args, selected):
        self._selected = selected

    def exec(self):
        return QDialog.DialogCode.Accepted

    def selected(self, kind):
        return self._selected


@pytest.mark.parametrize("kind", [SyncKind.DATA, SyncKind.STYLE])
def test_sync_dispatches_only_selected_items(monkeypatch, kind, qgis_application):
    loader = FakeLoader()
    provider = LayerTreeMenuProvider(
        FakeInterface(), LayerLockRegistry(), loader=loader
    )
    data_items = [
        UploadableLayerItem(
            RanaLayerRef("project", "first.gpkg", descriptor_id="desc-1"),
            Path("first.gpkg"),
            "first",
            "project",
        ),
        UploadableLayerItem(
            RanaLayerRef("project", "second.gpkg", descriptor_id="desc-2"),
            Path("second.gpkg"),
            "second",
            "project",
        ),
    ]
    style_items = [
        StyleUploadItem(
            data_type=DataType.vector,
            local_file_path="first.gpkg",
            file_ref_str="file first.gpkg",
            upload_func=lambda files: None,
            project_id="project",
            descriptor_id="desc-1",
        ),
        StyleUploadItem(
            data_type=DataType.vector,
            local_file_path="second.gpkg",
            file_ref_str="file second.gpkg",
            upload_func=lambda files: None,
            project_id="project",
            descriptor_id="desc-2",
        ),
    ]
    selected = (
        file_key("project", "desc-1", "first.gpkg")
        if kind is SyncKind.DATA
        else file_key("project", "desc-1", None)
    )

    monkeypatch.setattr(
        provider,
        "capture_data_items",
        lambda groups: data_items,
    )
    monkeypatch.setattr(
        provider,
        "capture_style_items",
        lambda groups: style_items,
    )
    monkeypatch.setattr(
        provider, "collect_sync_changes", lambda kind, groups: SyncChanges()
    )
    monkeypatch.setattr(
        layer_tree_menu,
        "SyncDialog",
        lambda *args, **kwargs: FakeSyncDialog(*args, selected={selected}),
    )

    provider.sync(kind, [])

    uploaded = loader.data_items if kind is SyncKind.DATA else loader.style_items
    assert uploaded == [data_items[0] if kind is SyncKind.DATA else style_items[0]]
