from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from osgeo import gdal
from qgis.core import QgsLayerTreeGroup, QgsRasterLayer, QgsVectorLayer
from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.layer_management.close_sync_prompt import (
    SyncPromptAction,
    collect_dirty_file_groups,
)
from rana_qgis_plugin.layer_management.layer_dirty_flags import DATA_SYNC_STATE_PROPERTY
from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef
from rana_qgis_plugin.layer_management.layer_sync_state import LayerSyncState
from rana_qgis_plugin.layer_management.layer_tree_menu import LayerTreeMenuProvider
from rana_qgis_plugin.layer_management.raster_dirty_evaluator import (
    capture_raster_baseline,
)
from rana_qgis_plugin.layer_management.sync_changes import SyncKind, file_key
from rana_qgis_plugin.layer_management.sync_lock import sync_key
from rana_qgis_plugin.layer_management.upload_lock import lock_jobs
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)
from rana_qgis_plugin.workers.upload import UploadJob
from tests.layer_management.sync_prompt_helpers import add_file_group, make_linked_layer


def create_test_raster(path: Path) -> None:
    """Create a small valid GeoTIFF for raster prompt tests."""
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset = gdal.GetDriverByName("GTiff").Create(str(path), 2, 2, 1, gdal.GDT_Byte)
    dataset.GetRasterBand(1).WriteRaster(0, 0, 2, 2, b"\x00" * 4)
    dataset = None


def test_collects_style_dirty_rana_file_groups(qgis_application):
    root = QgsLayerTreeGroup()
    dirty = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "dirty", "memory"), "dirty.gpkg"
    )
    clean = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "clean", "memory"), "clean.gpkg"
    )
    dirty.setCustomProperty("rana/style_dirty", True)
    dirty_group = add_file_group(root, "dirty-file", dirty)
    add_file_group(root, "clean-file", clean)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == [dirty_group]
    assert data_groups == []


def test_collects_vector_data_dirty_groups_and_ignores_unchanged_raster_data(
    qgis_application,
):
    root = QgsLayerTreeGroup()
    vector = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "vector", "memory"), "vector.gpkg"
    )
    raster = make_linked_layer(
        QgsRasterLayer("/vsimem/nonexistent.tif", "raster"), "raster.tif"
    )
    vector.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    raster.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)
    vector_group = add_file_group(root, "vector-file", vector)
    add_file_group(root, "raster-file", raster)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [vector_group]


def test_close_prompt_rechecks_raster_source_before_collecting_dirty_groups(
    tmp_path: Path, qgis_application
):
    root = QgsLayerTreeGroup()
    cache_dir = tmp_path / "cache"
    raster_path = cache_dir / "project" / "files" / "dem" / "dem.tif"
    create_test_raster(raster_path)
    raster = make_linked_layer(
        QgsRasterLayer(str(raster_path), "dem", "gdal"), "dem.tif"
    )
    assert isinstance(raster, QgsRasterLayer)
    raster_group = add_file_group(root, "raster-file", raster)

    with patch(
        "rana_qgis_plugin.layer_management.file_fingerprint.rana_cache_dir",
        return_value=str(cache_dir),
    ):
        capture_raster_baseline(raster)
        raster_path.write_bytes(raster_path.read_bytes() + b"changed")

        assert (
            raster.customProperty(DATA_SYNC_STATE_PROPERTY)
            == LayerSyncState.CLEAN.value
        )
        style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [raster_group]
    assert raster.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.DIRTY.value


def test_close_prompt_ignores_raster_when_source_is_unavailable(qgis_application):
    root = QgsLayerTreeGroup()
    raster = make_linked_layer(
        QgsRasterLayer("/vsimem/missing.tif", "raster"), "raster.tif"
    )
    add_file_group(root, "raster-file", raster)
    raster.setCustomProperty("rana/data_fingerprint", "stored-baseline")
    raster.setCustomProperty(DATA_SYNC_STATE_PROPERTY, LayerSyncState.DIRTY.value)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == []
    assert (
        raster.customProperty(DATA_SYNC_STATE_PROPERTY) == LayerSyncState.UNKNOWN.value
    )


def test_ignores_dirty_unlinked_layers_and_finds_nested_file_group(qgis_application):
    root = QgsLayerTreeGroup()
    folder = root.addGroup("folder")
    assert folder is not None
    unlinked = QgsVectorLayer("Point?crs=EPSG:4326", "unlinked", "memory")
    unlinked.setCustomProperty("rana/style_dirty", True)
    add_file_group(folder, "unlinked-file", unlinked)

    linked = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "linked", "memory"), "linked.gpkg"
    )
    linked.setCustomProperty("rana/data_sync_state", "dirty")
    linked_group = add_file_group(folder, "linked-file", linked)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == []
    assert data_groups == [linked_group]


def test_file_group_is_listed_once_when_multiple_layers_are_dirty(qgis_application):
    root = QgsLayerTreeGroup()
    group = root.addGroup("multi-layer-file")
    assert group is not None
    first = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "first", "memory"), "multi.gpkg"
    )
    second = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", "second", "memory"), "multi.gpkg"
    )
    group.addLayer(first)
    group.addLayer(second)
    first.setCustomProperty("rana/style_dirty", True)
    second.setCustomProperty("rana/style_dirty", True)

    style_groups, data_groups = collect_dirty_file_groups(root)

    assert style_groups == [group]
    assert data_groups == []


class FakeCloseSyncDialog:
    def __init__(self, *args, selected_style, selected_data):
        self._selected = {SyncKind.STYLE: selected_style, SyncKind.DATA: selected_data}

    def exec(self):
        return QDialog.DialogCode.Accepted

    def selected(self, kind):
        return self._selected[kind]

    def message(self):
        return "commit message"


class FakeCloseTaskManager:
    def __init__(self):
        self.tasks = []

    def addTask(self, task):
        self.tasks.append(task)


@pytest.fixture
def close_sync(monkeypatch, qgis_application):
    manager = FakeCloseTaskManager()
    monkeypatch.setattr(
        "rana_qgis_plugin.loader.QgsApplication.taskManager",
        staticmethod(lambda: manager),
    )
    monkeypatch.setattr("rana_qgis_plugin.loader.prepare_style_items", lambda items: [])
    loader = Loader(MagicMock())
    loader.verify_style_target = lambda item, layers: True
    uploads = []

    def record_upload(items, message=None):
        job = UploadJob("project", Path("file.gpkg"), "https://upload", {})
        job.sync_key = sync_key("project", "file.gpkg")
        locks, warnings = lock_jobs([job], loader.layer_lock_registry)
        for lock in locks.values():
            lock.release()
        uploads.append((message, warnings))

    loader.upload_existing_files = record_upload
    menu = LayerTreeMenuProvider(
        MagicMock(),
        loader.layer_lock_registry,
        ApiErrorSignals(),
        loader=loader,
    )
    return SimpleNamespace(manager=manager, loader=loader, uploads=uploads, menu=menu)


def close_sync_items(file_id: str = "file.gpkg", style: bool = True, data: bool = True):
    style_items = (
        [
            StyleUploadItem(
                data_type=DataType.vector,
                local_file_path=file_id,
                file_ref_str=f"file {file_id}",
                upload_func=lambda files: None,
                project_id="project",
                descriptor_id="descriptor",
                file_id=file_id,
            )
        ]
        if style
        else []
    )
    data_items = (
        [
            UploadableLayerItem(
                RanaLayerRef("project", file_id, descriptor_id="descriptor"),
                Path(file_id),
                "layer",
                "project",
            )
        ]
        if data
        else []
    )
    return style_items, data_items


def run_close_sync(close_sync, style_items, data_items, selected_style, selected_data):
    selected_style_keys = (
        {file_key("project", "descriptor", None)} if selected_style else set()
    )
    selected_data_keys = (
        {file_key("project", "descriptor", "file.gpkg")} if selected_data else set()
    )
    with patch(
        "rana_qgis_plugin.layer_management.close_sync_prompt.SyncDialog",
        lambda *args, **kwargs: FakeCloseSyncDialog(
            selected_style=selected_style_keys, selected_data=selected_data_keys
        ),
    ):
        SyncPromptAction(close_sync.menu).prompt_and_dispatch(
            style_items, data_items, MagicMock()
        )


def test_close_sync_data_waits_for_style_completion(close_sync):
    style_items, data_items = close_sync_items()

    run_close_sync(close_sync, style_items, data_items, True, True)

    assert close_sync.uploads == []
    style_task = close_sync.manager.tasks[0]
    style_task.taskCompleted.emit()
    assert close_sync.uploads == [("commit message", [])]


def test_close_sync_data_waits_for_style_termination(close_sync):
    style_items, data_items = close_sync_items()

    run_close_sync(close_sync, style_items, data_items, True, True)
    assert close_sync.uploads == []
    close_sync.manager.tasks[0].taskTerminated.emit()

    assert close_sync.uploads == [("commit message", [])]


def test_close_sync_data_uploads_immediately_when_style_not_started(close_sync):
    close_sync.loader.verify_style_target = lambda item, layers: False
    style_items, data_items = close_sync_items()

    run_close_sync(close_sync, style_items, data_items, True, True)

    assert close_sync.manager.tasks == []
    assert close_sync.uploads == [("commit message", [])]


def test_close_sync_data_uploads_immediately_when_no_style_selected(close_sync):
    style_items, data_items = close_sync_items()

    run_close_sync(close_sync, style_items, data_items, False, True)

    assert close_sync.manager.tasks == []
    assert close_sync.uploads == [("commit message", [])]
