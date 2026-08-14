from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.utils.api import RanaPostError


def make_loader():
    communication = MagicMock()
    return Loader(communication), communication


class TestRenameItem:
    @patch("rana_qgis_plugin.loader._has_sibling_file", return_value=False)
    @patch("rana_qgis_plugin.loader.move_file")
    def test_rename_file_calls_move_file(self, mock_move, _):
        loader, _ = make_loader()
        result = loader.rename_item(
            "proj1", "folder/old.tif", "new.tif", is_folder=False
        )

        assert result is None
        mock_move.assert_called_once_with(
            "proj1",
            params={
                "source_path": "folder/old.tif",
                "destination_path": "folder/new.tif",
            },
        )

    @patch("rana_qgis_plugin.loader._has_sibling_folder", return_value=False)
    @patch("rana_qgis_plugin.loader.move_directory")
    def test_rename_folder_calls_move_directory(self, mock_move, _):
        loader, _ = make_loader()
        result = loader.rename_item("proj1", "parent/old/", "new", is_folder=True)

        assert result is None
        mock_move.assert_called_once_with(
            "proj1",
            params={"source_path": "parent/old/", "destination_path": "parent/new/"},
        )

    @patch("rana_qgis_plugin.loader._has_sibling_file", return_value=False)
    @patch("rana_qgis_plugin.loader.move_file")
    def test_rename_file_emits_signal_on_success(self, mock_move, _):
        loader, _ = make_loader()
        signal_args = []
        loader.item_renamed.connect(lambda *args: signal_args.append(args))

        loader.rename_item("proj1", "folder/old.tif", "new.tif", is_folder=False)

        assert signal_args == [("folder/old.tif", "folder/new.tif", False)]

    @patch("rana_qgis_plugin.loader._has_sibling_file", return_value=False)
    @patch(
        "rana_qgis_plugin.loader.move_file",
        side_effect=RanaPostError("server error", "", {}),
    )
    def test_rename_file_returns_error_on_api_failure(self, mock_move, _):
        loader, _ = make_loader()
        signal_args = []
        loader.item_renamed.connect(lambda *args: signal_args.append(args))

        result = loader.rename_item(
            "proj1", "folder/old.tif", "new.tif", is_folder=False
        )

        assert result == "server error"
        assert signal_args == []

    def test_rename_rejects_empty_name(self):
        loader, _ = make_loader()
        assert (
            loader.rename_item("proj1", "folder/old.tif", "", is_folder=False)
            is not None
        )
        assert (
            loader.rename_item("proj1", "folder/old.tif", "  ", is_folder=False)
            is not None
        )

    @patch("rana_qgis_plugin.loader._has_sibling_file", return_value=True)
    def test_rename_file_rejects_duplicate(self, _):
        loader, _ = make_loader()
        result = loader.rename_item(
            "proj1", "folder/old.tif", "existing.tif", is_folder=False
        )
        assert result == "File 'existing.tif' already exists."

    @patch("rana_qgis_plugin.loader._has_sibling_folder", return_value=True)
    def test_rename_folder_rejects_duplicate(self, _):
        loader, _ = make_loader()
        result = loader.rename_item("proj1", "parent/old/", "existing", is_folder=True)
        assert result == "Folder 'existing' already exists."


class TestDeleteFile:
    @patch("rana_qgis_plugin.loader.delete_tenant_project_file")
    def test_delete_calls_api(self, mock_delete):
        loader, _ = make_loader()
        result = loader.delete_file("proj1", "folder/file.tif")

        assert result is None
        mock_delete.assert_called_once_with("proj1", params={"path": "folder/file.tif"})

    @patch("rana_qgis_plugin.loader.delete_tenant_project_file")
    def test_delete_emits_signal_on_success(self, mock_delete):
        loader, _ = make_loader()
        signal_args = []
        loader.item_deleted.connect(lambda *args: signal_args.append(args))

        loader.delete_file("proj1", "folder/file.tif")

        assert signal_args == [("folder/file.tif", False)]

    @patch(
        "rana_qgis_plugin.loader.delete_tenant_project_file",
        side_effect=RanaPostError("delete failed", "", {}),
    )
    def test_delete_returns_error_on_failure(self, mock_delete):
        loader, _ = make_loader()
        signal_args = []
        loader.item_deleted.connect(lambda *args: signal_args.append(args))

        result = loader.delete_file("proj1", "folder/file.tif")

        assert result == "delete failed"
        assert signal_args == []
