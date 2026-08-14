from unittest.mock import MagicMock, patch

from rana_qgis_plugin.loader import Loader


def make_loader():
    communication = MagicMock()
    return Loader(communication), communication


class TestRenameItem:
    @patch("rana_qgis_plugin.loader.move_file", return_value=True)
    def test_rename_file_calls_move_file(self, mock_move):
        loader, _ = make_loader()
        result = loader.rename_item(
            "proj1", "folder/old.tif", "new.tif", is_folder=False
        )

        assert result is True
        mock_move.assert_called_once_with(
            "proj1",
            params={
                "source_path": "folder/old.tif",
                "destination_path": "folder/new.tif",
            },
        )

    @patch("rana_qgis_plugin.loader.move_directory", return_value=True)
    def test_rename_folder_calls_move_directory(self, mock_move):
        loader, _ = make_loader()
        result = loader.rename_item("proj1", "parent/old/", "new", is_folder=True)

        assert result is True
        mock_move.assert_called_once_with(
            "proj1",
            params={"source_path": "parent/old/", "destination_path": "parent/new/"},
        )

    @patch("rana_qgis_plugin.loader.move_file", return_value=True)
    def test_rename_file_emits_signal_on_success(self, mock_move):
        loader, _ = make_loader()
        signal_args = []
        loader.item_renamed.connect(lambda *args: signal_args.append(args))

        loader.rename_item("proj1", "folder/old.tif", "new.tif", is_folder=False)

        assert signal_args == [("folder/old.tif", "folder/new.tif", False)]

    @patch("rana_qgis_plugin.loader.move_file", return_value=False)
    def test_rename_file_no_signal_on_failure(self, mock_move):
        loader, _ = make_loader()
        signal_args = []
        loader.item_renamed.connect(lambda *args: signal_args.append(args))

        result = loader.rename_item(
            "proj1", "folder/old.tif", "new.tif", is_folder=False
        )

        assert result is False
        assert signal_args == []


class TestDeleteFile:
    @patch("rana_qgis_plugin.loader.delete_tenant_project_file", return_value=True)
    def test_delete_calls_api(self, mock_delete):
        loader, _ = make_loader()
        result = loader.delete_file("proj1", "folder/file.tif")

        assert result is True
        mock_delete.assert_called_once_with("proj1", params={"path": "folder/file.tif"})

    @patch("rana_qgis_plugin.loader.delete_tenant_project_file", return_value=True)
    def test_delete_emits_signal_on_success(self, mock_delete):
        loader, _ = make_loader()
        signal_args = []
        loader.item_deleted.connect(lambda *args: signal_args.append(args))

        loader.delete_file("proj1", "folder/file.tif")

        assert signal_args == [("folder/file.tif", False)]

    @patch("rana_qgis_plugin.loader.delete_tenant_project_file", return_value=False)
    def test_delete_no_signal_on_failure(self, mock_delete):
        loader, _ = make_loader()
        signal_args = []
        loader.item_deleted.connect(lambda *args: signal_args.append(args))

        result = loader.delete_file("proj1", "folder/file.tif")

        assert result is False
        assert signal_args == []
