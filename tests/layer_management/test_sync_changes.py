from qgis.core import QgsVectorLayer

from rana_qgis_plugin.layer_management.sync_changes import SyncChanges, SyncKind
from tests.layer_management.sync_prompt_helpers import fk, make_linked_layer

BOTH = set(SyncKind)


def make_vector(
    name: str,
    file_id: str,
    dirty: bool = False,
    style: bool = False,
    data_state: str | None = None,
    project_id: str = "project",
):
    layer = make_linked_layer(
        QgsVectorLayer("Point?crs=EPSG:4326", name, "memory"), file_id, project_id
    )
    if dirty:
        data_state = "dirty"
    if data_state:
        layer.setCustomProperty("rana/data_sync_state", data_state)
    if style:
        layer.setCustomProperty("rana/style_dirty", True)
    return layer


def test_collect_changes_splits_data_and_style(qgis_application):
    layers = [
        make_vector("data_only", "a.gpkg", dirty=True),
        make_vector("style_only", "a.gpkg", style=True),
        make_vector("both", "a.gpkg", dirty=True, style=True),
        make_vector("clean", "a.gpkg"),
    ]

    assert SyncChanges.from_layers(layers, BOTH) == SyncChanges(
        data={fk("a.gpkg"): ["both", "data_only"]},
        style={fk("a.gpkg"): ["both", "style_only"]},
    )


def test_collect_changes_only_collects_requested_kinds(qgis_application):
    layers = [make_vector("both", "a.gpkg", dirty=True, style=True)]

    assert SyncChanges.from_layers(layers, {SyncKind.DATA}) == SyncChanges(
        data={fk("a.gpkg"): ["both"]}
    )
    assert SyncChanges.from_layers(layers, {SyncKind.STYLE}) == SyncChanges(
        style={fk("a.gpkg"): ["both"]}
    )
    assert SyncChanges.from_layers(layers, set()) == SyncChanges()


def test_collect_changes_omits_kinds_without_changes(qgis_application):
    layers = [make_vector("dirty", "b.gpkg", dirty=True)]

    assert SyncChanges.from_layers(layers, BOTH) == SyncChanges(
        data={fk("b.gpkg"): ["dirty"]}
    )


def test_collect_changes_keeps_the_full_file_path(qgis_application):
    layers = [make_vector("dirty", "folder/sub/b.gpkg", dirty=True)]

    assert SyncChanges.from_layers(layers, BOTH) == SyncChanges(
        data={fk("folder/sub/b.gpkg"): ["dirty"]}
    )


def test_unknown_data_state_is_only_counted_when_requested(qgis_application):
    layers = [make_vector("unknown", "a.gpkg", data_state="unknown")]

    assert SyncChanges.from_layers(layers, BOTH) == SyncChanges()
    assert SyncChanges.from_layers(
        layers, BOTH, include_unknown_data=True
    ) == SyncChanges(data={fk("a.gpkg"): ["unknown"]})


def test_merge_combines_layers_per_file_sorted_into_a_new_object():
    first = SyncChanges(data={fk("a.gpkg"): ["l2"]})
    second = SyncChanges(
        data={fk("a.gpkg"): ["l1", "l2"], fk("b.gpkg"): ["l3"]},
        style={fk("c.gpkg"): ["l4"]},
    )

    merged = first.merge(second)

    assert merged == SyncChanges(
        data={fk("a.gpkg"): ["l1", "l2"], fk("b.gpkg"): ["l3"]},
        style={fk("c.gpkg"): ["l4"]},
    )
    assert first == SyncChanges(data={fk("a.gpkg"): ["l2"]})


def test_for_kind_keeps_only_that_kind():
    changes = SyncChanges(data={fk("a.gpkg"): ["l1"]}, style={fk("b.gpkg"): ["l2"]})

    assert changes.for_kind(SyncKind.DATA) == SyncChanges(data={fk("a.gpkg"): ["l1"]})
    assert changes.for_kind(SyncKind.STYLE) == SyncChanges(style={fk("b.gpkg"): ["l2"]})


def test_is_empty_and_file_count():
    assert SyncChanges().is_empty()
    changes = SyncChanges(data={fk("a.gpkg"): ["l1"]}, style={fk("a.gpkg"): ["l1"]})
    assert not changes.is_empty()
    assert changes.file_count() == 1


def test_same_file_path_in_different_projects_is_not_merged(qgis_application):
    layers = [
        make_vector("one", "results.gpkg", dirty=True, project_id="p1"),
        make_vector("two", "results.gpkg", dirty=True, project_id="p2"),
    ]

    changes = SyncChanges.from_layers(layers, BOTH)

    assert changes.data == {
        fk("results.gpkg", "p1"): ["one"],
        fk("results.gpkg", "p2"): ["two"],
    }
    assert changes.file_count() == 2
