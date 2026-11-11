from qgis.core import QgsRasterLayer, QgsVectorLayer

from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef, set_rana_refs
from rana_qgis_plugin.layer_management.sync_changes import (
    ChangedFile,
    ChangedLayer,
    SyncChanges,
    SyncFileKey,
    SyncKind,
    file_key,
)
from tests.layer_management.sync_prompt_helpers import fk, make_changes

BOTH = set(SyncKind)


def make_vector(
    name: str,
    file_id: str,
    dirty: bool = False,
    style: bool = False,
    data_state: str | None = None,
    project_id: str = "project",
    descriptor_id: str | None = None,
    geometry: str = "Point",
):
    uri = f"{geometry}?crs=EPSG:4326" if geometry != "None" else "None"
    layer = QgsVectorLayer(uri, name, "memory")
    set_rana_refs(layer, RanaLayerRef(project_id, file_id, descriptor_id=descriptor_id))
    if dirty:
        data_state = "dirty"
    if data_state:
        layer.setCustomProperty("rana/data_sync_state", data_state)
    if style:
        layer.setCustomProperty("rana/style_dirty", True)
    return layer


def test_from_layers_splits_data_and_style(qgis_application):
    layers = [
        make_vector("data_only", "a.gpkg", dirty=True),
        make_vector("style_only", "a.gpkg", style=True, descriptor_id="a.gpkg"),
        make_vector("both", "a.gpkg", dirty=True, style=True, descriptor_id="a.gpkg"),
        make_vector("clean", "a.gpkg"),
    ]

    assert SyncChanges.from_layers(layers, BOTH) == make_changes(
        data={fk("a.gpkg"): ["both", "data_only"]},
        style={fk("a.gpkg"): ["both", "style_only"]},
    )


def test_from_layers_only_collects_requested_kinds(qgis_application):
    layers = [
        make_vector("both", "a.gpkg", dirty=True, style=True, descriptor_id="a.gpkg")
    ]

    assert SyncChanges.from_layers(layers, {SyncKind.DATA}) == make_changes(
        data={fk("a.gpkg"): ["both"]}
    )
    assert SyncChanges.from_layers(layers, {SyncKind.STYLE}) == make_changes(
        style={fk("a.gpkg"): ["both"]}
    )
    assert SyncChanges.from_layers(layers, set()) == SyncChanges()


def test_from_layers_ignores_a_layer_collected_twice(qgis_application):
    """A file group dirty for both kinds is in both group lists of the close route."""
    layer = make_vector(
        "both", "a.gpkg", dirty=True, style=True, descriptor_id="a.gpkg"
    )

    changes = SyncChanges.from_layers([layer, layer], BOTH)

    assert changes == make_changes(
        data={fk("a.gpkg"): ["both"]}, style={fk("a.gpkg"): ["both"]}
    )


def test_project_ids_lists_every_project_with_changes(qgis_application):
    layers = [
        make_vector("a", "a.gpkg", dirty=True, project_id="p1"),
        make_vector("b", "b.gpkg", style=True, descriptor_id="b.gpkg", project_id="p2"),
    ]

    assert SyncChanges.from_layers(layers, BOTH).project_ids() == {"p1", "p2"}


def test_from_layers_keeps_the_full_file_path_as_the_file_path(qgis_application):
    layers = [make_vector("dirty", "folder/sub/b.gpkg", dirty=True)]

    changes = SyncChanges.from_layers(layers, BOTH)

    assert changes.data == {
        fk("folder/sub/b.gpkg"): ChangedFile(
            "folder/sub/b.gpkg", "vector", (ChangedLayer("dirty", "point"),)
        )
    }


def test_from_layers_reports_layer_and_file_icon_types(qgis_application):
    layers = [
        make_vector("points", "a.gpkg", dirty=True, geometry="Point"),
        make_vector("lines", "a.gpkg", dirty=True, geometry="LineString"),
        make_vector("polygons", "b.gpkg", dirty=True, geometry="Polygon"),
        make_vector("table", "c.gpkg", dirty=True, geometry="None"),
    ]

    changes = SyncChanges.from_layers(layers, BOTH)

    assert changes.data[fk("a.gpkg")] == ChangedFile(
        "a.gpkg",
        "vector",
        (ChangedLayer("lines", "linestring"), ChangedLayer("points", "point")),
    )
    assert changes.data[fk("b.gpkg")].layers == (ChangedLayer("polygons", "polygon"),)
    assert changes.data[fk("c.gpkg")].layers == (ChangedLayer("table", "table"),)


def test_from_layers_uses_raster_icon_for_raster_files(qgis_application):
    layer = QgsRasterLayer("/does/not/exist.tif", "elevation", "gdal")
    set_rana_refs(layer, RanaLayerRef("project", "elevation.tif"))
    layer.setCustomProperty("rana/data_sync_state", "dirty")

    changes = SyncChanges.from_layers([layer], BOTH)

    assert changes.data == {
        fk("elevation.tif"): ChangedFile(
            "elevation.tif", "raster", (ChangedLayer("elevation", "raster"),)
        )
    }


def test_style_skips_layers_without_descriptor(qgis_application):
    layers = [
        make_vector("no_descriptor", "a.gpkg", style=True),
        make_vector("with_descriptor", "a.gpkg", style=True, descriptor_id="desc-1"),
    ]

    changes = SyncChanges.from_layers(layers, {SyncKind.STYLE})

    assert set(changes.style) == {SyncFileKey("project", "desc-1")}
    assert changes.style[SyncFileKey("project", "desc-1")].layers == (
        ChangedLayer("with_descriptor", "point"),
    )


def test_unknown_data_state_is_only_counted_when_requested(qgis_application):
    layers = [make_vector("unknown", "a.gpkg", data_state="unknown")]

    assert SyncChanges.from_layers(layers, BOTH) == SyncChanges()
    assert SyncChanges.from_layers(
        layers, BOTH, include_unknown_data=True
    ) == make_changes(data={fk("a.gpkg"): ["unknown"]})


def test_file_key_uses_descriptor_then_file_id():
    assert file_key("p", "desc", "a.gpkg") == SyncFileKey("p", "desc")
    assert file_key("p", None, "a.gpkg") == fk("a.gpkg", "p")


def test_file_key_is_none_without_project_or_reference():
    assert file_key(None, "desc", "a.gpkg") is None
    assert file_key("p", None, None) is None


def test_merge_combines_layers_per_file_sorted_into_a_new_object():
    first = make_changes(data={fk("a.gpkg"): ["l2"]})
    second = make_changes(
        data={fk("a.gpkg"): ["l1", "l2"], fk("b.gpkg"): ["l3"]},
        style={fk("c.gpkg"): ["l4"]},
    )

    merged = first.merge(second)

    assert merged == make_changes(
        data={fk("a.gpkg"): ["l1", "l2"], fk("b.gpkg"): ["l3"]},
        style={fk("c.gpkg"): ["l4"]},
    )
    assert first == make_changes(data={fk("a.gpkg"): ["l2"]})


def test_for_kind_keeps_only_that_kind():
    changes = make_changes(data={fk("a.gpkg"): ["l1"]}, style={fk("b.gpkg"): ["l2"]})

    assert changes.for_kind(SyncKind.DATA) == make_changes(data={fk("a.gpkg"): ["l1"]})
    assert changes.for_kind(SyncKind.STYLE) == make_changes(
        style={fk("b.gpkg"): ["l2"]}
    )


def test_is_empty_and_file_count():
    assert SyncChanges().is_empty()
    changes = make_changes(data={fk("a.gpkg"): ["l1"]}, style={fk("a.gpkg"): ["l1"]})
    assert not changes.is_empty()
    assert changes.file_count() == 1


def test_same_file_path_in_different_projects_is_not_merged(qgis_application):
    layers = [
        make_vector("one", "results.gpkg", dirty=True, project_id="p1"),
        make_vector("two", "results.gpkg", dirty=True, project_id="p2"),
    ]

    changes = SyncChanges.from_layers(layers, BOTH)

    assert set(changes.data) == {fk("results.gpkg", "p1"), fk("results.gpkg", "p2")}
    assert changes.file_count() == 2


def test_project_names_come_from_the_layers(qgis_application):
    layers = [
        make_vector("a", "a.gpkg", dirty=True, project_id="p1"),
        make_vector("b", "b.gpkg", dirty=True, project_id="p2"),
    ]
    set_rana_refs(layers[0], RanaLayerRef("p1", "a.gpkg", project_name="Alpha"))
    changes = SyncChanges.from_layers(layers, BOTH)

    assert changes.project_names == {"p1": "Alpha"}
    assert changes.for_kind(SyncKind.DATA).project_names == {"p1": "Alpha"}
    assert changes.merge(SyncChanges()).project_names == {"p1": "Alpha"}
