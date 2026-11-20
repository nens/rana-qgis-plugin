from pathlib import Path

import pytest
from osgeo import ogr, osr
from qgis.core import QgsProject, QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.sync_lock import LayerLockRegistry, sync_key
from rana_qgis_plugin.layer_management.upload_lock import (
    UPLOAD_LOCK_PROPERTY,
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

    locks[0].release()

    assert not roads.readOnly()
    assert water.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) is None
    assert not registry.is_locked(job.sync_key)


def test_release_twice_is_harmless_and_skips_removed_layers(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    water = add_layer(f"{gpkg}|layername=water", "water")
    registry = LayerLockRegistry()
    locks, _ = lock_jobs([make_job(gpkg)], registry)
    QgsProject.instance().removeMapLayer(water.id())

    locks[0].release()
    locks[0].release()

    assert not roads.readOnly()


def test_job_with_editable_layer_is_refused(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    roads.startEditing()
    registry = LayerLockRegistry()
    job = make_job(gpkg)

    locks, warnings = lock_jobs([job], registry)

    assert locks == []
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
    assert len(locks) == 1
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

    locks, warnings = lock_jobs([make_job(path)], registry)

    assert layers_for_file(path) == [raster]
    assert warnings == []
    assert locks[0].layer_ids == []
    assert raster.customProperty(UPLOAD_LOCK_PROPERTY) is None


def test_restore_stale_upload_locks_clears_leftover_property(gpkg):
    roads = add_layer(f"{gpkg}|layername=roads", "roads")
    roads.setReadOnly(True)
    roads.setCustomProperty(UPLOAD_LOCK_PROPERTY, "false")

    restore_stale_upload_locks(QgsProject.instance())

    assert not roads.readOnly()
    assert roads.customProperty(UPLOAD_LOCK_PROPERTY) is None
