import io
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
    PreparedStyleItem,
    RasterStyleBuilder,
    StyleUploadTask,
    VectorStyleBuilderAllLayers,
    VectorStyleBuilderSingleLayer,
    make_file_style_upload_item,
    prepare_style_item,
    write_style_files,
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
    files = write_style_files(builder.prepare(), tmp_path)

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    assert qml_zip.exists()
    with zipfile.ZipFile(qml_zip) as archive:
        assert {"roads.qml", "water.qml"}.issubset(archive.namelist())


def test_vector_builder_single_layer_only_writes_requested_qml(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)

    builder = VectorStyleBuilderSingleLayer(
        str(source), "layers.gpkg", LiveLayerSource(layers), "roads"
    )
    files = write_style_files(builder.prepare(), tmp_path)

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    with zipfile.ZipFile(qml_zip) as archive:
        assert archive.namelist() == ["roads.qml"]


def test_raster_builder_writes_qml_and_colormap(tmp_path, qgis_application):
    source = tmp_path / "elevation.tif"
    create_raster(source)

    layer = QgsRasterLayer(str(source), "elevation", "gdal")
    assert layer.isValid()
    QgsProject.instance().addMapLayer(layer)

    builder = RasterStyleBuilder(str(source), "elevation.tif", LiveLayerSource([layer]))
    files = write_style_files(builder.prepare(), tmp_path)

    names = {name for _, name, _, _ in files}
    assert "qml.zip" in names
    assert "colormap.json" in names
    for _, name, path, _ in files:
        assert Path(path).exists()
        if name == "colormap.json":
            json.loads(Path(path).read_text())


def test_vector_builder_uses_snapshot_after_project_is_cleared(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = capture_layer_styles(layers)

    QgsProject.instance().clear()

    builder = VectorStyleBuilderAllLayers(str(source), "layers.gpkg", layer_source)
    assert builder.validate_layers()
    files = write_style_files(builder.prepare(), tmp_path)

    qml_zip = next(Path(path) for _, name, path, _ in files if name == "qml.zip")
    with zipfile.ZipFile(qml_zip) as archive:
        assert {"roads.qml", "water.qml"}.issubset(archive.namelist())
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
    names = {name for _, name, _, _ in write_style_files(builder.prepare(), tmp_path)}
    assert {"qml.zip", "colormap.json"}.issubset(names)
    layer_source.discard()


def test_discard_removes_the_captured_qml_directory(tmp_path, qgis_application):
    source = tmp_path / "layers.gpkg"
    layers = open_two_vector_layers(source)
    layer_source = capture_layer_styles(layers)
    qml_dir = layer_source.qml_dir
    assert qml_dir.exists()

    layer_source.discard()
    layer_source.discard()

    assert not qml_dir.exists()
    assert layer_source.layers == []


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


def test_prepare_style_item_captures_missing_layer_on_the_item(
    tmp_path, qgis_application
):
    source = tmp_path / "layers.gpkg"
    item = make_file_style_upload_item(
        "descriptor",
        DataType.vector,
        str(source),
        "file layers.gpkg",
        LiveLayerSource([]),
        layer_in_file="missing",
    )

    prepared = prepare_style_item(item)

    assert prepared.style is None
    assert prepared.error == "Layer not found for file layers.gpkg"


def test_upload_task_writes_prepared_style_and_reports_failures(
    tmp_path, qgis_application
):
    from rana_qgis_plugin.workers.styling import PreparedStyle

    uploaded: list[dict[str, bytes]] = []

    def capture(files: list) -> None:
        uploaded.append({name: Path(path).read_bytes() for _, name, path, _ in files})

    good = PreparedStyleItem(
        "good",
        capture,
        style=PreparedStyle(
            qml_files={"roads.qml": b"<qgis/>"},
            json_files=[("style", {"version": 8})],
            png_files=[("sprite", b"\x89PNG")],
        ),
    )
    bad = PreparedStyleItem("bad", capture, error="conversion broke")
    task = StyleUploadTask([good, bad])
    failures: list[tuple[str, str]] = []
    task.item_failed.connect(lambda name, error: failures.append((name, error)))

    assert task.run() is False

    assert failures == [("bad", "conversion broke")]
    (files,) = uploaded
    assert list(files) == ["qml.zip", "style.json", "sprite.png"]
    with zipfile.ZipFile(io.BytesIO(files["qml.zip"])) as archive:
        assert archive.read("roads.qml") == b"<qgis/>"
    assert json.loads(files["style.json"]) == {"version": 8}
    assert files["sprite.png"] == b"\x89PNG"
