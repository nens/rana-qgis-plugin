from unittest.mock import patch

from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.simulation.rana_folder_picker import RanaFolderPicker
from rana_qgis_plugin.utils.api import RanaFetchError

PROJECT = {"id": "project-id", "name": "My project"}


def make_list_folders(tree, fail_paths=()):
    """Fake listing: *tree* maps a parent path to (name, type) pairs."""
    calls = []

    def list_folders(project_id, params=None):
        path = (params or {}).get("path", "")
        calls.append(path)
        if path in fail_paths:
            raise RanaFetchError("boom", "url", {})
        return [
            {
                "id": f"{path}{name}/" if kind == "directory" else f"{path}{name}",
                "type": kind,
            }
            for name, kind in tree.get(path, [])
        ]

    list_folders.calls = calls
    return list_folders


def open_picker(qtbot, tree, start_folder="", fail_paths=()):
    list_folders = make_list_folders(tree, fail_paths)
    picker = RanaFolderPicker(PROJECT, start_folder, list_folders=list_folders)
    qtbot.addWidget(picker)
    return picker, list_folders


TREE = {
    "": [("models", "directory"), ("readme.txt", "file")],
    "models/": [("river", "directory")],
    "models/river/": [("results", "directory")],
}


def test_only_folders_are_listed(qtbot):
    picker, _ = open_picker(qtbot, TREE)

    root = picker.tree.topLevelItem(0)
    names = [root.child(i).text(0) for i in range(root.childCount())]

    assert names == ["models"]


def test_project_root_is_the_only_top_level_item(qtbot):
    picker, _ = open_picker(qtbot, TREE)

    assert picker.tree.topLevelItemCount() == 1
    assert picker.tree.topLevelItem(0).text(0) == "My project"


def test_start_folder_is_expanded_and_selected(qtbot):
    picker, _ = open_picker(qtbot, TREE, start_folder="models/river/")

    assert picker.selected_folder() == "models/river/"
    assert picker.tree.currentItem().isExpanded()


def test_expanding_loads_children_once(qtbot):
    picker, list_folders = open_picker(qtbot, TREE)
    models = picker.tree.topLevelItem(0).child(0)

    models.setExpanded(True)
    models.setExpanded(False)
    models.setExpanded(True)

    assert list_folders.calls.count("models/") == 1


def test_selected_folder_returns_project_path_of_selection(qtbot):
    picker, _ = open_picker(qtbot, TREE, start_folder="models/")
    river = picker.tree.topLevelItem(0).child(0).child(0)

    picker.tree.setCurrentItem(river)

    assert picker.selected_folder() == "models/river/"


def test_selected_folder_is_empty_for_project_root(qtbot):
    picker, _ = open_picker(qtbot, TREE)

    picker.tree.setCurrentItem(picker.tree.topLevelItem(0))

    assert picker.selected_folder() == ""


def test_expand_error_shows_message_and_keeps_dialog_usable(qtbot):
    picker, _ = open_picker(qtbot, TREE, fail_paths={"models/"})
    models = picker.tree.topLevelItem(0).child(0)

    models.setExpanded(True)

    assert not picker.error_label.isHidden()
    assert "boom" in picker.error_label.text()
    assert picker.tree.topLevelItemCount() == 1


def test_initial_load_error_closes_dialog_with_message(qtbot):
    with patch(
        "rana_qgis_plugin.simulation.rana_folder_picker.QMessageBox.warning"
    ) as warning:
        picker, _ = open_picker(qtbot, TREE, fail_paths={""})

    assert picker.result() == QDialog.DialogCode.Rejected
    warning.assert_called_once()
