from pathlib import Path

import pytest
from osgeo import ogr, osr
from qgis.core import QgsFeature, QgsProject, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry, sync_key
from rana_qgis_plugin.layer_management.upload_lock import (
    UPLOAD_LOCK_PROPERTY,
    FileLock,
    layers_for_file,
    lock_jobs,
    restore_stale_upload_locks,
)
from rana_qgis_plugin.workers.upload import UploadJob


def create_vector_file(path: Path, driver: str, table_names: list[str]) -> None:
    data_source = ogr.GetDriverByName(driver).CreateDataSource(str(path))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    for name in table_names:
        data_source.CreateLayer(name, spatial_reference, ogr.wkbPoint)
    data_source = None


def add_layer(source: str, name: str) -> QgsVectorLayer:
    layer = QgsVectorLayer(source, name, "ogr")
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)
    return layer


def make_job(path: Path) -> UploadJob:
    job = UploadJob("project", path, "https://upload", {})
    job.sync_key = sync_key("project", path.name)
    return job


@pytest.fixture(autouse=True)
def clean_project(qgis_application):
    yield
    QgsProject.instance().clear()


@pytest.fixture
def gpkg(tmp_path: Path) -> Path:
    path = tmp_path / "layers.gpkg"
    create_vector_file(path, "GPKG", ["roads", "water"])
    return path


def test_layers_for_file_matches_all_geopackage_tables(gpkg, tmp_path):
    other = tmp_path / "other.gpkg"
    create_vector_file(other, "GPKG", ["roads"])
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    water = add_layer(f"{gpkg}|layername=water", "water")
    add_layer(f"{other}|layername=roads", "other roads")

    assert set(layers_for_file(gpkg)) == {roads, water}


def test_layers_for_file_matches_shapefile_and_ignores_other_files(tmp_path):
    shapefile = tmp_path / "roads.shp"
    create_vector_file(shapefile, "ESRI Shapefile", ["roads"])
    layer = add_layer(str(shapefile), "roads")

    assert layers_for_file(shapefile) == [layer]
    assert layers_for_file(tmp_path / "unrelated.shp") == []


def test_lock_makes_layers_read_only_and_release_restores_previous_state(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    water = add_layer(f"{gpkg}|layername=water", "water")
    water.setReadOnly(True)
    registry = LayerLockRegistry()
    job = make_job(gpkg)

    locks, warnings = lock_jobs([job], registry)

    assert warnings == []
    assert roads.readOnly() and water.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) == "false"
    assert registry.is_locked(job.sync_key)

    locks[job.sync_key].release()

    assert not roads.readOnly()
    assert water.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) is None
    assert not registry.is_locked(job.sync_key)


def test_release_skips_removed_layers(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    water = add_layer(f"{gpkg}|layername=water", "water")
    registry = LayerLockRegistry()
    job = make_job(gpkg)
    locks, _ = lock_jobs([job], registry)
    QgsProject.instance().removeMapLayer(water.id())

    locks[job.sync_key].release()

    assert not roads.readOnly()


def test_second_release_leaves_a_newer_lock_on_the_same_file_intact(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    registry = LayerLockRegistry()
    job = make_job(gpkg)
    old_locks, _ = lock_jobs([job], registry)
    old_locks[job.sync_key].release()
    new_locks, _ = lock_jobs([job], registry)

    old_locks[job.sync_key].release()

    assert registry.is_locked(job.sync_key)
    assert roads.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) == "false"
    new_locks[job.sync_key].release()
    assert not roads.readOnly()


def test_repeated_download_lock_release_leaves_a_newer_lock_intact():
    """A download lock is released from several task signals; only the first counts.

    The loader connects the same lock's release to file_downloaded,
    taskCompleted and taskTerminated, so it can be called more than once.
    The registry only stores keys and does not know who holds them, so a
    repeated release must not free a key that a newer lock has since taken.
    """
    registry = LayerLockRegistry()
    key = sync_key("project", "file")
    assert registry.acquire(key)
    download_lock = FileLock(key, registry, [])

    # First release (file_downloaded): frees the key.
    download_lock.release()
    assert not registry.is_locked(key)

    # A newer lock (e.g. an upload of the same file) takes the key.
    assert registry.acquire(key)

    # Later signals (taskCompleted, taskTerminated) release the old lock again.
    # Because the old lock already released, these must do nothing.
    download_lock.release()
    download_lock.release()

    assert registry.is_locked(key), "old lock freed the newer lock's key"


def test_job_with_editable_layer_is_refused(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    roads.startEditing()
    roads.addFeature(QgsFeature(roads.fields()))
    registry = LayerLockRegistry()
    job = make_job(gpkg)

    locks, warnings = lock_jobs([job], registry)

    assert locks == {}
    assert warnings == ["layers.gpkg: save or discard your edits first."]
    assert not registry.is_locked(job.sync_key)
    roads.rollBack()


def test_job_with_held_key_is_dropped_but_other_jobs_are_locked(gpkg, tmp_path):
    other = tmp_path / "other.gpkg"
    create_vector_file(other, "GPKG", ["roads"])
    add_layer(f"{gpkg}|layername=roads", "roads")
    other_roads = add_layer(f"{other}|layername=roads", "other roads")
    registry = LayerLockRegistry()
    assert registry.acquire(sync_key("project", gpkg.name))

    locks, warnings = lock_jobs([make_job(gpkg), make_job(other)], registry)

    assert warnings == ["layers.gpkg is already being synced."]
    assert list(locks) == [sync_key("project", other.name)]
    assert other_roads.readOnly()


def test_failure_part_way_releases_what_was_taken(gpkg, tmp_path):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    registry = LayerLockRegistry()
    broken = UploadJob("project", tmp_path / "broken.gpkg", "https://upload", {})

    with pytest.raises(ValueError):
        lock_jobs([make_job(gpkg), broken], registry)

    assert not roads.readOnly()
    assert not registry.is_locked(sync_key("project", gpkg.name))


def test_rasters_are_matched_but_not_locked(tmp_path):
    from osgeo import gdal

    path = tmp_path / "grid.tif"
    gdal.GetDriverByName("GTiff").Create(str(path), 4, 4, 1, gdal.GDT_Byte)
    raster = QgsRasterLayer(str(path), "grid")
    QgsProject.instance().addMapLayer(raster)
    registry = LayerLockRegistry()

    job = make_job(path)
    locks, warnings = lock_jobs([job], registry)

    assert layers_for_file(path) == [raster]
    assert warnings == []
    assert locks[job.sync_key].layer_ids == []
    assert raster.customProperty(UPLOAD_LOCK_PROPERTY) is None


def test_restore_stale_upload_locks_clears_leftover_property(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    roads.setReadOnly(True)
    roads.setCustomProperty(UPLOAD_LOCK_PROPERTY, "false")

    restore_stale_upload_locks(QgsProject.instance())

    assert not roads.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) is None
