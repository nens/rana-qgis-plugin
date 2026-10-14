import json
import zipfile
from pathlib import Path

from qgis.core import QgsProject, QgsRasterLayer

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    open_rana_vector_layer,
)
from rana_qgis_plugin.utils.data_models import DataType
from rana_qgis_plugin.workers.style_layers import (
    LiveLayerSource,
    capture_layer_styles,
)
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


def create_raster(path: Path) -> None:
    from osgeo import gdal, osr

    raster = gdal.GetDriverByName("GTiff").Create(str(path), 4, 4, 1, gdal.GDT_Byte)
    raster.SetGeoTransform((0, 1, 0, 0, 0, -1))
    spatial_reference = osr.SpatialReference()
    spatial_reference.ImportFromEPSG(4326)
    raster.SetProjection(spatial_reference.ExportToWkt())
    raster.GetRasterBand(1).Fill(1)
    raster = None


def project_layers_for(source: Path) -> list:
    return [
        layer
        for layer in QgsProject.instance().mapLayers().values()
        if str(source) in layer.source()
    ]


def open_two_vector_layers(source: Path) -> list:
    create_geopackage(source, ["roads", "water"])
    ref = RanaLayerRef("project", "layers.gpkg", "descriptor")
    open_rana_vector_layer(str(source), "roads", ["Project", "layers.gpkg"], ref)
    open_rana_vector_layer(str(source), "water", ["Project", "layers.gpkg"], ref)
    return project_layers_for(source)


def test_vector_builder_all_layers_writes_qml_zip(tmp_path, qgis_application):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)

    builder = VectorStyleBuilderAllLayers(
        str(source), "layers.gpkg", LiveLayerSource(layers)
    )
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
    layers = open_two_vector_layers(source)

    builder = VectorStyleBuilderSingleLayer(
        str(source), "layers.gpkg", LiveLayerSource(layers), "roads"
    )
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    files = builder.get_files()

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    with zipfile.ZipFile(qml_zip) as archive:
        assert archive.namelist() == ["roads.qml"]
    builder.clean()


def test_raster_builder_writes_qml_and_colormap(tmp_path, qgis_application):
    source = tmp_path / "elevation.tif"
    create_raster(source)

    layer = QgsRasterLayer(str(source), "elevation", "gdal")
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)

    builder = RasterStyleBuilder(str(source), "elevation.tif", LiveLayerSource([layer]))
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


def test_vector_builder_uses_snapshot_after_project_is_cleared(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = capture_layer_styles(layers)

    QgsProject.instance().clear()

    builder = VectorStyleBuilderAllLayers(str(source), "layers.gpkg", layer_source)
    assert builder.validate_layers()
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    files = builder.get_files()

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    with zipfile.ZipFile(qml_zip) as archive:
        assert {"roads.qml", "water.qml"}.issubset(archive.namelist())
    builder.clean()
    layer_source.discard()


def test_snapshot_preserves_the_captured_symbol_colour(tmp_path, qgis_application):
    from qgis.core import QgsMarkerSymbol, QgsSingleSymbolRenderer

    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    roads = next(layer for layer in layers if layer.name() == "roads")
    roads.setRenderer(
        QgsSingleSymbolRenderer(
            QgsMarkerSymbol.createSimple({"name": "star", "color": "255,0,0,255"})
        )
    )

    layer_source = capture_layer_styles(layers)
    QgsProject.instance().clear()

    restored = next(layer for layer in layer_source.layers if layer.name() == "roads")
    assert restored.renderer().symbol().color().name() == "#ff0000"
    layer_source.discard()


def test_raster_snapshot_survives_project_clear(tmp_path, qgis_application):
    source = tmp_path / "elevation.tif"
    create_raster(source)
    layer = QgsRasterLayer(str(source), "elevation", "gdal")
    QgsProject.instance().addMapLayer(layer)

    layer_source = capture_layer_styles([layer])
    QgsProject.instance().clear()

    builder = RasterStyleBuilder(str(source), "elevation.tif", layer_source)
    assert builder.validate_layers()
    builder.tempdir.mkdir(parents=True, exist_ok=True)
    names = {name for _, name, _, _ in builder.get_files()}
    assert {"qml.zip", "colormap.json"}.issubset(names)
    builder.clean()
    layer_source.discard()


def test_discard_removes_the_captured_qml_directory(tmp_path, qgis_application):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = capture_layer_styles(layers)
    qml_dir = layer_source.qml_dir
    assert qml_dir.exists()

    layer_source.discard()

    assert not qml_dir.exists()


def test_live_layer_source_is_not_affected_by_discard(tmp_path, qgis_application):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = LiveLayerSource(layers)

    layer_source.discard()

    assert len(layer_source.layers) == 2


def test_make_file_style_upload_item_carries_the_layer_source(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = LiveLayerSource(layers)

    item = make_file_style_upload_item(
        "descriptor",
        DataType.vector,
        str(source),
        "file layers.gpkg",
        layer_source,
        project_id="project",
    )

    assert item.layer_source is layer_source
