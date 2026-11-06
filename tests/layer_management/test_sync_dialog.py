from pathlib import Path

from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtWidgets import QTreeWidgetItem

from rana_qgis_plugin.layer_management.layer_manager import (
    RanaLayerRef,
    get_rana_refs,
    set_rana_refs,
)
from rana_qgis_plugin.layer_management.sync_changes import (
    SyncChanges,
    SyncKind,
    file_key,
)
from rana_qgis_plugin.layer_management.sync_prompt_dialog import SyncDialog
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)


def make_layer(name: str, file_id: str, descriptor_id: str, style: bool = False):
    layer = QgsVectorLayer("Point?crs=EPSG:4326", name, "memory")
    set_rana_refs(layer, RanaLayerRef("project", file_id, descriptor_id=descriptor_id))
    layer.setCustomProperty("rana/data_sync_state", "dirty")
    if style:
        layer.setCustomProperty("rana/style_dirty", True)
    return layer


def make_dialog(layers, kind=SyncKind.DATA) -> SyncDialog:
    changes = SyncChanges.from_layers(layers, {kind}, include_unknown_data=True)
    return SyncDialog(None, "Sync", "Continue sync", "Cancel sync", changes)


def find_item(dialog: SyncDialog, text: str) -> QTreeWidgetItem:
    matches = dialog.tree.findItems(
        text, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive
    )
    assert len(matches) == 1, f"expected one row named {text!r}"
    return matches[0]


def check_state(dialog: SyncDialog, text: str) -> Qt.CheckState:
    return find_item(dialog, text).checkState(0)


def test_everything_is_checked_by_default(qgis_application):
    dialog = make_dialog(
        [make_layer("a", "a.gpkg", "d1"), make_layer("b", "sub/b.gpkg", "d2")]
    )

    assert dialog.selected(SyncKind.DATA) == {
        file_key("project", "d1", None),
        file_key("project", "d2", None),
    }
    assert dialog.confirm_button.isEnabled()


def test_unchecking_a_file_removes_it_from_selected(qgis_application):
    dialog = make_dialog(
        [make_layer("a", "a.gpkg", "d1"), make_layer("b", "b.gpkg", "d2")]
    )

    find_item(dialog, "a.gpkg").setCheckState(0, Qt.CheckState.Unchecked)

    assert dialog.selected(SyncKind.DATA) == {file_key("project", "d2", None)}


def test_unchecking_a_folder_unchecks_its_files(qgis_application):
    dialog = make_dialog(
        [
            make_layer("a", "folder/a.gpkg", "d1"),
            make_layer("b", "folder/sub/b.gpkg", "d2"),
            make_layer("c", "other.gpkg", "d3"),
        ]
    )

    find_item(dialog, "folder").setCheckState(0, Qt.CheckState.Unchecked)

    assert dialog.selected(SyncKind.DATA) == {file_key("project", "d3", None)}


def test_parents_show_partial_state_when_some_children_are_checked(qgis_application):
    dialog = make_dialog(
        [make_layer("a", "folder/a.gpkg", "d1"), make_layer("b", "folder/b.gpkg", "d2")]
    )

    find_item(dialog, "a.gpkg").setCheckState(0, Qt.CheckState.Unchecked)

    assert check_state(dialog, "folder") == Qt.CheckState.PartiallyChecked
    assert check_state(dialog, "project") == Qt.CheckState.PartiallyChecked
    assert check_state(dialog, "Data changes:") == Qt.CheckState.PartiallyChecked


def test_tree_nests_files_under_project_and_folders(qgis_application):
    dialog = make_dialog([make_layer("b", "folder/sub/b.gpkg", "d2")])

    file_item = find_item(dialog, "b.gpkg")
    assert file_item.parent().text(0) == "sub"
    assert file_item.parent().parent().text(0) == "folder"
    assert file_item.parent().parent().parent().text(0) == "project"
    assert file_item.parent().parent().parent().parent().text(0) == "Data changes:"


def test_layers_are_listed_under_their_file_and_not_checkable(qgis_application):
    dialog = make_dialog([make_layer("roads", "roads.gpkg", "d1")])

    layer_item = find_item(dialog, "roads")

    assert layer_item.parent().text(0) == "roads.gpkg"
    assert not layer_item.flags() & Qt.ItemFlag.ItemIsUserCheckable


def test_confirm_is_disabled_when_nothing_is_checked(qgis_application):
    dialog = make_dialog([make_layer("a", "a.gpkg", "d1")])

    find_item(dialog, "a.gpkg").setCheckState(0, Qt.CheckState.Unchecked)

    assert not dialog.confirm_button.isEnabled()


def test_upload_item_keys_match_the_tree_rows(qgis_application):
    layer = make_layer("roads", "folder/roads.gpkg", "desc-1", style=True)
    dialog = make_dialog([layer])
    ref = get_rana_refs(layer)
    assert ref is not None

    data_item = UploadableLayerItem(ref, Path("roads.gpkg"), "roads", "project")
    style_item = StyleUploadItem(
        data_type=DataType.vector,
        local_file_path="roads.gpkg",
        file_ref_str="file folder/roads.gpkg",
        upload_func=lambda files: None,
        project_id="project",
        descriptor_id="desc-1",
    )
    style_dialog = make_dialog([layer], kind=SyncKind.STYLE)

    data_key = file_key(
        data_item.rana_ref.project_id,
        data_item.rana_ref.descriptor_id,
        data_item.rana_ref.file_id,
    )
    style_key = file_key(style_item.project_id, style_item.descriptor_id, None)

    assert data_key in dialog.selected(SyncKind.DATA)
    assert style_key in style_dialog.selected(SyncKind.STYLE)


def test_without_kinds_the_tree_starts_at_the_project(qgis_application):
    changes = SyncChanges.from_layers(
        [make_layer("a", "folder/a.gpkg", "d1")], {SyncKind.DATA}
    )

    dialog = SyncDialog(
        None, "Sync", "Continue sync", "Cancel sync", changes, show_kinds=False
    )

    assert dialog.tree.topLevelItemCount() == 1
    assert dialog.tree.topLevelItem(0).text(0) == "project"
    assert dialog.selected(SyncKind.DATA) == {file_key("project", "d1", None)}


def test_unchecking_works_without_kinds(qgis_application):
    changes = SyncChanges.from_layers(
        [make_layer("a", "a.gpkg", "d1"), make_layer("b", "b.gpkg", "d2")],
        {SyncKind.DATA},
    )
    dialog = SyncDialog(
        None, "Sync", "Continue sync", "Cancel sync", changes, show_kinds=False
    )

    dialog.tree.topLevelItem(0).setCheckState(0, Qt.CheckState.Unchecked)

    assert dialog.selected(SyncKind.DATA) == set()
    assert not dialog.confirm_button.isEnabled()


def test_project_node_shows_the_project_name_when_known(qgis_application):
    changes = SyncChanges.from_layers(
        [make_layer("a", "a.gpkg", "d1")], {SyncKind.DATA}
    )

    dialog = SyncDialog(
        None,
        "Sync",
        "Continue sync",
        "Cancel sync",
        changes,
        project_names={"project": "Flood study"},
    )

    assert find_item(dialog, "Flood study").parent().text(0) == "Data changes:"
    assert dialog.tree.findItems("project", Qt.MatchFlag.MatchRecursive) == []


def test_project_and_folder_rows_have_icons(qgis_application):
    dialog = make_dialog([make_layer("a", "folder/a.gpkg", "d1")])

    assert not find_item(dialog, "project").icon(0).isNull()
    assert not find_item(dialog, "folder").icon(0).isNull()
