from pathlib import Path
from unittest.mock import Mock, PropertyMock, patch

import pytest
from qgis.core import QgsProject, QgsVectorLayer

import rana_qgis_plugin.layer_management.layer_manager as lm

# --- Test rana refs ---


def test_rana_refs_round_trip():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")

    lm.set_rana_refs(
        layer,
        lm.RanaLayerRef("project", "folder/file.gpkg", "descriptor", "layer"),
    )

    assert lm.get_rana_refs(layer) == lm.RanaLayerRef(
        project_id="project",
        file_id="folder/file.gpkg",
        descriptor_id="descriptor",
        layer_id="layer",
    )
    assert lm.is_rana_linked(layer)


def test_unlinked_layer_has_no_rana_refs():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")

    assert lm.get_rana_refs(layer) is None
    assert not lm.is_rana_linked(layer)


def test_clear_rana_refs():
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")
    lm.set_rana_refs(layer, lm.RanaLayerRef("project", "file.gpkg"))

    lm.clear_rana_refs(layer)

    assert lm.get_rana_refs(layer) is None


# --- Test layer management ---


def _create_test_gpkg(tmp_path: Path, name: str, *layer_names: str) -> Path:
    """Create a minimal GeoPackage with named point layers."""
    from osgeo import ogr, osr

    gpkg_path = tmp_path / name
    drv = ogr.GetDriverByName("GPKG")
    ds = drv.CreateDataSource(str(gpkg_path))
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    for layer_name in layer_names:
        geom_type = ogr.wkbLineString if "line" in layer_name else ogr.wkbPoint
        ds.CreateLayer(layer_name, srs, geom_type)
    ds = None
    return gpkg_path


def _create_test_raster(tmp_path: Path, name: str) -> Path:
    """Create a minimal GeoTIFF raster."""
    from osgeo import gdal, osr

    path = tmp_path / name
    driver = gdal.GetDriverByName("GTiff")
    ds = driver.Create(str(path), 4, 4, 1, gdal.GDT_Byte)
    srs = osr.SpatialReference()
    srs.ImportFromEPSG(4326)
    ds.SetProjection(srs.ExportToWkt())
    ds.SetGeoTransform([0, 1, 0, 0, 0, -1])
    ds.GetRasterBand(1).WriteRaster(0, 0, 4, 4, b"\x00" * 16)
    ds = None
    return path


@pytest.fixture(autouse=True)
def clean_project(qgis_application):
    """Start each test with an empty QGIS project."""
    QgsProject.instance().clear()
    yield
    QgsProject.instance().clear()


REF = lm.RanaLayerRef(
    project_id="proj-1",
    file_id="folder/sub/data.gpkg",
    descriptor_id="desc-1",
)
PARENTS = ["Project A", "files", "folder", "sub", "data.gpkg"]


class TestFindOrCreateRanaGroups:
    def test_creates_nested_groups(self):
        group = lm.find_or_create_rana_groups(PARENTS, "proj-1")
        assert group.name() == "data.gpkg"
        root = QgsProject.instance().layerTreeRoot()
        top = root.findGroup("Project A")
        assert top is not None
        assert top.customProperty("rana/project_id") == "proj-1"
        assert top.customProperty("rana/path_segment") == "Project A"

    def test_reuses_existing_groups(self):
        group1 = lm.find_or_create_rana_groups(PARENTS, "proj-1")
        group2 = lm.find_or_create_rana_groups(PARENTS, "proj-1")
        assert group1 is group2

    def test_different_project_creates_separate_groups(self):
        group1 = lm.find_or_create_rana_groups(["Project A"], "proj-1")
        group2 = lm.find_or_create_rana_groups(["Project A"], "proj-2")
        assert group1 is not group2
        root = QgsProject.instance().layerTreeRoot()
        assert len([c for c in root.children() if c.name() == "Project A"]) == 2


def test_open_vector_layer(tmp_path):
    gpkg = _create_test_gpkg(tmp_path, "test.gpkg", "points")
    layer = lm.open_rana_vector_layer(str(gpkg), "points", PARENTS, REF)
    assert layer is not None
    assert layer.isValid()
    assert layer.name() == "points"
    refs = lm.get_rana_refs(layer)
    assert refs == REF
    group = lm.find_or_create_rana_groups(PARENTS, "proj-1")
    child_names = [
        c.layer().name() for c in group.children() if hasattr(c, "layer") and c.layer()
    ]
    assert ["points"] == child_names
    # check repeat open does not create a new layer
    lm.open_rana_vector_layer(str(gpkg), "points", PARENTS, REF)
    group = lm.find_or_create_rana_groups(PARENTS, "proj-1")
    child_names = [
        c.layer().name() for c in group.children() if hasattr(c, "layer") and c.layer()
    ]
    assert ["points"] == child_names


def test_open_vector_layer_invalid(tmp_path):
    layer = lm.open_rana_vector_layer(
        str(tmp_path / "nonexistent.gpkg"), "nope", PARENTS, REF
    )
    assert layer is None


def test_open_rana_vector_layers(tmp_path):
    gpkg = _create_test_gpkg(tmp_path, "test.gpkg", "points", "lines")
    layers = lm.open_rana_vector_layers(str(gpkg), ["points", "lines"], PARENTS, REF)
    assert len(layers) == 2
    assert {l.name() for l in layers} == {"points", "lines"}


def test_open_raster(tmp_path):
    tif = _create_test_raster(tmp_path, "dem.tif")
    layer = lm.open_rana_raster(str(tif), PARENTS, REF)
    assert layer is not None
    assert layer.isValid()
    assert layer.name() == "dem.tif"
    assert lm.get_rana_refs(layer) == REF


def test_open_raster_invalid(tmp_path):
    layer = lm.open_rana_raster(str(tmp_path / "nonexistent.tif"), PARENTS, REF)
    assert layer is None


@pytest.mark.parametrize(
    "wip_replace_requested, expected_filename",
    [(True, "wip.gpkg"), (False, "schema.gpkg")],
)
def test_open_rana_schematisation_tags_loaded_group(
    wip_replace_requested: bool, expected_filename: str
):
    revision = Mock()
    type(revision).schematisation_db_filepath = PropertyMock(
        return_value="/tmp/schema.gpkg"
    )
    type(revision).schematisation_dir = PropertyMock(return_value="/tmp")
    wip_revision = Mock()
    type(wip_revision).schematisation_db_filepath = PropertyMock(
        return_value="/tmp/wip.gpkg"
    )
    type(wip_revision).schematisation_dir = PropertyMock(return_value="/tmp")

    local_schematisation = type(
        "LocalSchematisation",
        (),
        {
            "id": 42,
            "revisions": {7: revision},
            "wip_revision": wip_revision,
        },
    )()
    with patch.object(lm, "load_local_schematisation") as load:
        load.return_value = "Rana schematisation: schema"
        lm.open_rana_schematisation(
            Mock(),
            "Project",
            "project-id",
            local_schematisation,
            7,
            wip_replace_requested=wip_replace_requested,
            parents=["Project", "files", "folder"],
        )

    group = lm.find_or_create_rana_groups(["Project", "files", "folder"], "project-id")
    group = group.findGroup("Rana schematisation: schema")
    assert group is not None
    assert group.customProperty("rana/schematisation_id") == 42
    assert group.customProperty("rana/revision_number") == 7
    assert (
        group.customProperty("rana/schematisation_db_filepath")
        == "/tmp/" + expected_filename
    )
    assert load.call_args.kwargs["parents"] == [
        "Project",
        "files",
        "folder",
    ]
