import json
import zipfile
from pathlib import Path

from qgis.core import QgsProject, QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    open_rana_vector_layer,
)
from rana_qgis_plugin.utils.data_models import DataType
from rana_qgis_plugin.workers.styling import (
    RasterStyleBuilder,
    VectorStyleBuilderAllLayers,
    VectorStyleBuilderSingleLayer,
    make_file_style_upload_item,
)


def create_geopackage(path: Path, layer_names: list[str]) -> None:
    from osgeo import ogr, osr

    driver = ogr.GetDriverByName("GPKG")
    data_source = driver.CreateDataSource(str(path))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    for layer_name in layer_names:
        data_source.CreateLayer(layer_name, spatial_reference, ogr.wkbPoint)
    data_source = None


def test_vector_builder_all_layers_writes_qml_zip(tmp_path, qgis_application):
    source = tmp_path / "layers.gpkg"
    create_geopackage(source, ["roads", "water"])
    ref = RanaLayerRef("project", "layers.gpkg", "descriptor")
    open_rana_vector_layer(str(source), "roads", ["Project", "layers.gpkg"], ref)
    open_rana_vector_layer(str(source), "water", ["Project", "layers.gpkg"], ref)

    builder = VectorStyleBuilderAllLayers(str(source), "layers.gpkg")
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    files = builder.get_files()

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    assert qml_zip.exists()
    with zipfile.ZipFile(qml_zip) as archive:
        assert {"roads.qml", "water.qml"}.issubset(archive.namelist())
    builder.clean()


def test_vector_builder_single_layer_only_writes_requested_qml(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    create_geopackage(source, ["roads", "water"])
    ref = RanaLayerRef("project", "layers.gpkg", "descriptor")
    open_rana_vector_layer(str(source), "roads", ["Project", "layers.gpkg"], ref)
    open_rana_vector_layer(str(source), "water", ["Project", "layers.gpkg"], ref)

    builder = VectorStyleBuilderSingleLayer(str(source), "layers.gpkg", "roads")
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    files = builder.get_files()

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    with zipfile.ZipFile(qml_zip) as archive:
        assert archive.namelist() == ["roads.qml"]
    builder.clean()


def test_raster_builder_writes_qml_and_colormap(tmp_path, qgis_application):
    from osgeo import gdal, osr

    source = tmp_path / "elevation.tif"
    raster = gdal.GetDriverByName("GTiff").Create(str(source), 4, 4, 1, gdal.GDT_Byte)
    raster.SetGeoTransform((0, 1, 0, 0, 0, -1))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    raster.SetProjection(spatial_reference.ExportToWkt())
    raster.GetRasterBand(1).Fill(1)
    raster = None

    layer = QgsRasterLayer(str(source), "elevation", "gdal")
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)

    builder = RasterStyleBuilder(str(source), "elevation.tif")
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    files = builder.get_files()

    names = {name for _, name, _, _ in files}
    assert "qml.zip" in names
    assert "colormap.json" in names
    for _, name, path, _ in files:
        assert Path(path).exists()
        if name == "colormap.json":
            json.loads(Path(path).read_text())
    builder.clean()
