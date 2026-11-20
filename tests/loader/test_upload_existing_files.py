from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from osgeo import ogr, osr
from qgis.core import QgsProject, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.sync_lock import sync_key
from rana_qgis_plugin.layer_management.upload_lock import lock_jobs
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.data_models import UploadableLayerItem
from rana_qgis_plugin.workers.upload import UploadJob, UploadPreparationResult


@pytest.fixture(autouse=True)
def clean_project(qgis_application):
    QgsProject.instance().clear()
    yield
    QgsProject.instance().clear()


@pytest.fixture
def loader() -> Loader:
    return Loader(MagicMock())


def linked_vector_layer(path: Path) -> QgsVectorLayer:
    """Create a GeoPackage and add its layer, linked to Rana as `path.name`."""
    data_source = ogr.GetDriverByName("GPKG").CreateDataSource(str(path))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    data_source.CreateLayer("roads", spatial_reference, ogr.wkbPoint)
    data_source = None
    layer = QgsVectorLayer(f"{path}|layername=roads", path.stem, "ogr")
    assert layer.isValid()
    set_rana_refs(layer, RanaLayerRef("project", path.name))
    QgsProject.instance().addMapLayer(layer)
    return layer


def job_for(path: Path) -> UploadJob:
    job = UploadJob("project", path, "https://upload", {"path": path.name})
    job.sync_key = sync_key("project", path.name)
    return job


def test_failed_file_is_unlocked_and_logged(loader, tmp_path):
    path = tmp_path / "roads.gpkg"
    layer = linked_vector_layer(path)
    locks, _ = lock_jobs([job_for(path)], loader.layer_lock_registry)
    assert layer.readOnly()

    loader.handle_data_file_failed(str(path), "connection error", locks[0])

    assert not layer.readOnly()
    assert not loader.layer_lock_registry.is_locked(sync_key("project", path.name))
    loader.communication.log_err.assert_called_once()


def test_releasing_file_locks_unlocks_all_files_and_is_repeatable(loader, tmp_path):
    paths = [tmp_path / "first.gpkg", tmp_path / "second.gpkg"]
    layers = [linked_vector_layer(path) for path in paths]
    locks, _ = lock_jobs([job_for(p) for p in paths], loader.layer_lock_registry)
    assert all(layer.readOnly() for layer in layers)

    loader.release_file_locks(locks)
    loader.release_file_locks(locks)

    assert not any(layer.readOnly() for layer in layers)
    for path in paths:
        assert not loader.layer_lock_registry.is_locked(sync_key("project", path.name))


@pytest.fixture
def server() -> Iterator[SimpleNamespace]:
    """Fake the Rana server answers and the QGIS task manager for one upload."""
    fake = SimpleNamespace(prepared={}, task_manager=MagicMock(), prepare=None)
    with (
        patch.object(Loader, "verify_data_target", return_value=True),
        patch(
            "rana_qgis_plugin.loader.prepare_existing_file_upload",
            side_effect=lambda project, file, **kwargs: fake.prepared[file["id"]],
        ) as fake.prepare,
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=fake.task_manager,
        ),
    ):
        yield fake


def upload(loader: Loader, *paths: Path) -> None:
    loader.upload_existing_files(
        [
            UploadableLayerItem(RanaLayerRef("project", p.name), p, p.stem, "Project")
            for p in paths
        ]
    )


def test_error_while_starting_the_task_unlocks_everything(loader, server, tmp_path):
    path = tmp_path / "roads.gpkg"
    layer = linked_vector_layer(path)
    server.prepared[path.name] = UploadPreparationResult(job_for(path))
    server.task_manager.addTask.side_effect = RuntimeError("boom")

    upload(loader, path)

    assert not layer.readOnly()
    assert not loader.layer_lock_registry.is_locked(sync_key("project", path.name))
    loader.communication.bar_error.assert_called_once()
    assert "boom" in loader.communication.log_err.call_args.args[0]


def test_file_without_a_job_is_never_locked(loader, server, tmp_path):
    uploaded_path, skipped_path = tmp_path / "up.gpkg", tmp_path / "skipped.gpkg"
    uploaded = linked_vector_layer(uploaded_path)
    skipped = linked_vector_layer(skipped_path)
    server.prepared[uploaded_path.name] = UploadPreparationResult(
        job_for(uploaded_path)
    )
    server.prepared[skipped_path.name] = UploadPreparationResult(None, "not ready")

    upload(loader, uploaded_path, skipped_path)

    assert uploaded.readOnly()
    assert not skipped.readOnly()
    assert not loader.layer_lock_registry.is_locked(sync_key("project", "skipped.gpkg"))


def test_file_with_a_layer_in_edit_mode_is_refused_before_preparing(
    loader, server, tmp_path
):
    path = tmp_path / "roads.gpkg"
    layer = linked_vector_layer(path)
    server.prepared[path.name] = UploadPreparationResult(job_for(path))
    layer.startEditing()

    upload(loader, path)

    server.prepare.assert_not_called()
    server.task_manager.addTask.assert_not_called()
    assert (
        "Save or discard your edits first"
        in (loader.communication.bar_warn.call_args.args[0])
    )
    assert layer.isEditable()
    layer.rollBack()
