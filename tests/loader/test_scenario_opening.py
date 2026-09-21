from pathlib import Path
from unittest.mock import MagicMock, patch

from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.workers.download import (
    RanaRawResultsDownloader,
    RanaResultDownloader,
)

from .helpers import (
    linked_descriptor,
    make_loader,
    scenario_descriptor,
    scenario_request,
)


def test_open_scenario_results_downloads_raw_results_without_3di_link():
    loader, communication = make_loader()
    request = scenario_request()

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=scenario_descriptor({}, scenario_id=None),
        ),
        patch.object(RanaRawResultsDownloader, "resolve_url"),
        patch.object(loader, "submit_scenario_result_download") as submit,
    ):
        loader.open_scenario_results(request)

    communication.bar_info.assert_called_once()
    submit.assert_called_once()
    downloaders = submit.call_args.args[1]
    assert len(downloaders) == 1
    assert isinstance(downloaders[0], RanaRawResultsDownloader)
    assert downloaders[0].download_context.filename == "results.zip"


def test_open_scenario_results_shows_dialog_and_builds_selected_downloaders(
    tmp_path,
):
    loader, _ = make_loader()
    request = scenario_request()
    browser = MagicMock()
    browser.exec.return_value = QDialog.DialogCode.Accepted
    browser.get_selected_results.return_value = (
        [1],
        -9999.0,
        10.0,
        "EPSG:4326",
    )
    browser.get_download_raw_result.return_value = True
    results = [
        {
            "id": 1,
            "name": "max water depth (file)",
            "attachment_url": "https://example.com/max-depth.tif",
        }
    ]

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=linked_descriptor(),
        ),
        patch(
            "rana_qgis_plugin.utils.scenario.get_tenant_file_descriptor_view",
            return_value=results,
        ),
        patch("rana_qgis_plugin.loader.ResultBrowser", return_value=browser),
        patch.object(RanaRawResultsDownloader, "resolve_url"),
        patch(
            "rana_qgis_plugin.workers.download.get_local_results_dir",
            return_value=str(tmp_path),
        ),
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value=str(tmp_path)),
        patch.object(loader, "submit_scenario_result_download") as submit,
    ):
        loader.open_scenario_results(request)

    browser.exec.assert_called_once_with()
    submit.assert_called_once()
    downloaders = submit.call_args.args[1]
    assert len(downloaders) == 2
    assert isinstance(downloaders[0], RanaRawResultsDownloader)
    assert isinstance(downloaders[1], RanaResultDownloader)


def test_open_scenario_results_cancellation_does_not_submit_download():
    loader, _ = make_loader()
    request = scenario_request()
    browser = MagicMock()
    browser.exec.return_value = QDialog.DialogCode.Rejected

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=linked_descriptor(),
        ),
        patch(
            "rana_qgis_plugin.utils.scenario.get_tenant_file_descriptor_view",
            return_value=[],
        ),
        patch("rana_qgis_plugin.loader.ResultBrowser", return_value=browser),
        patch.object(loader, "submit_scenario_result_download") as submit,
    ):
        loader.open_scenario_results(request)

    submit.assert_not_called()


def test_open_scenario_results_resolves_in_background_when_metadata_is_incomplete():
    loader, _ = make_loader()
    request = scenario_request()
    task_manager = MagicMock()
    api = object()

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=scenario_descriptor({"id": 42}),
        ),
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=api),
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
        patch("rana_qgis_plugin.loader.ScenarioResolveTask") as resolve_task,
    ):
        loader.open_scenario_results(request)

    resolve_task.assert_called_once()
    assert resolve_task.call_args.args[1] is api
    task_manager.addTask.assert_called_once_with(resolve_task.return_value)


def test_open_items_dispatches_scenario_requests_in_batch():
    loader, _ = make_loader()
    request = scenario_request()

    with patch.object(loader, "open_scenario_results_batch") as open_batch:
        loader.open_items([request])

    open_batch.assert_called_once_with(request)


def test_batch_scenario_uses_raw_and_default_attached_result_without_dialog(
    tmp_path,
):
    loader, _ = make_loader()
    request = scenario_request()
    browser = MagicMock()
    results = [
        {
            "id": 1,
            "name": "max water depth (file)",
            "attachment_url": "https://example.com/max-depth.tif",
        }
    ]

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=linked_descriptor(),
        ),
        patch(
            "rana_qgis_plugin.utils.scenario.get_tenant_file_descriptor_view",
            return_value=results,
        ),
        patch("rana_qgis_plugin.loader.ResultBrowser", return_value=browser),
        patch.object(RanaRawResultsDownloader, "resolve_url"),
        patch(
            "rana_qgis_plugin.workers.download.get_local_results_dir",
            return_value=str(tmp_path),
        ),
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value=str(tmp_path)),
        patch.object(loader, "submit_scenario_result_download") as submit,
    ):
        loader.open_scenario_results_batch(request)

    browser.assert_not_called()
    submit.assert_called_once()
    downloaders = submit.call_args.args[1]
    assert len(downloaders) == 2
    assert isinstance(downloaders[0], RanaRawResultsDownloader)
    assert isinstance(downloaders[1], RanaResultDownloader)


def test_batch_scenario_skips_without_working_directory():
    loader, communication = make_loader()
    request = scenario_request()

    with patch("rana_qgis_plugin.loader.hcc_working_dir", return_value=""):
        loader.start_batch_scenario_result_download(
            request,
            MagicMock(has_3di_simulation=True),
        )

    communication.bar_warn.assert_called_once_with(
        "Skipping scenario because no 3Di working directory is configured."
    )


def test_batch_scenario_skips_when_default_result_is_missing():
    loader, communication = make_loader()
    request = scenario_request()

    continuation = loader.start_batch_scenario_result_download
    scenario = linked_descriptor()
    from rana_qgis_plugin.utils.scenario import ScenarioInfo

    with (
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp/3di"),
        patch(
            "rana_qgis_plugin.utils.scenario.get_tenant_file_descriptor_view",
            return_value=[],
        ),
    ):
        continuation(request, ScenarioInfo(scenario))
    communication.bar_warn.assert_called_once_with(
        "Skipping scenario because the default result is unavailable."
    )


def test_failed_scenario_download_does_not_open_results_analysis():
    loader, communication = make_loader()
    request = scenario_request()
    task = MagicMock()
    task.isCanceled.return_value = False
    task.failed_files = [("results.zip", "failed")]
    task_manager = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
        patch("rana_qgis_plugin.loader.DownloadTask", return_value=task),
        patch.object(
            loader, "load_scenario_results_in_results_analysis"
        ) as open_results,
    ):
        loader.submit_scenario_result_download(request, [MagicMock()])

    termination_callback = task.taskTerminated.connect.call_args.args[0]
    termination_callback()
    open_results.assert_not_called()
    communication.bar_error.assert_called_once_with(
        "Scenario results download failed for: results.zip"
    )


def test_scenario_download_completion_opens_results_analysis_once(tmp_path):
    loader, _ = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.dockwidget.isVisible.return_value = True

    with patch(
        "rana_qgis_plugin.loader.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        loader.load_scenario_results_in_results_analysis(
            str(tmp_path), {"name": "Project"}
        )

    results_analysis.load_result.assert_called_once_with(
        Path(tmp_path) / "results_3di.nc",
        Path(tmp_path) / "gridadmin.h5",
        project="Project",
    )


def test_scenario_download_task_completion_opens_results_analysis(tmp_path):
    loader, _ = make_loader()
    request = scenario_request()
    downloader = MagicMock()
    downloader.download_context.local_dir = tmp_path
    task_manager = MagicMock()
    task = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.loader.QgsApplication.taskManager",
            return_value=task_manager,
        ),
        patch("rana_qgis_plugin.loader.DownloadTask", return_value=task),
        patch.object(
            loader, "load_scenario_results_in_results_analysis"
        ) as open_results,
    ):
        loader.submit_scenario_result_download(request, [downloader])
        assert task.taskCompleted.connect.call_count == 2
        completion_callback = task.taskCompleted.connect.call_args_list[0].args[0]
        completion_callback()
        open_results.assert_called_once_with(str(tmp_path), request.project)
        task_manager.addTask.assert_called_once_with(task)


def test_scenario_download_warns_when_results_analysis_is_missing(tmp_path):
    loader, communication = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()

    with patch(
        "rana_qgis_plugin.loader.get_threedi_results_analysis_tool_instance",
        return_value=None,
    ):
        loader.load_scenario_results_in_results_analysis(
            str(tmp_path), {"name": "Project"}
        )

    communication.bar_warn.assert_called_once()


def test_scenario_download_falls_back_for_old_results_analysis_signature(tmp_path):
    loader, communication = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.dockwidget.isVisible.return_value = True
    results_analysis.load_result.side_effect = [
        TypeError("unexpected keyword argument 'project'"),
        None,
    ]

    with patch(
        "rana_qgis_plugin.loader.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        loader.load_scenario_results_in_results_analysis(
            str(tmp_path), {"name": "Project"}
        )

    assert results_analysis.load_result.call_count == 2
    communication.bar_warn.assert_called_once()
