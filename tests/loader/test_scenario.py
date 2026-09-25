from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.layer_management.layer_manager import (
    open_scenario_results_in_results_analysis,
)
from rana_qgis_plugin.utils.api import RanaFetchError
from rana_qgis_plugin.utils.data_models import OpenScenarioWmsRequest
from rana_qgis_plugin.workers.download import (
    RanaRawResultsDownloader,
    RanaResultDownloader,
)

from .helpers import make_loader, scenario_request


def test_open_scenario_wms_opens_descriptor_layers_in_wms_group():
    loader, communication = make_loader()
    request = scenario_wms_request()
    descriptor = {
        "links": [{"rel": "wms", "href": "https://example.test/wms"}],
        "meta": {"layers": [{"code": "depth"}]},
    }

    with (
        patch(
            "rana_qgis_plugin.loader.get_tenant_file_descriptor",
            return_value=descriptor,
        ),
        patch(
            "rana_qgis_plugin.loader.open_rana_wms", return_value=[MagicMock()]
        ) as open_wms,
    ):
        loader.open_scenario_wms(request)

    open_wms.assert_called_once_with(
        descriptor,
        descriptor["meta"]["layers"],
        ["Project", "files", "path", "to", "scenario", "wms"],
        "project",
    )
    communication.bar_error.assert_not_called()


def test_open_scenario_wms_batch_continues_after_failure():
    loader, communication = make_loader()
    requests = [scenario_wms_request(), scenario_wms_request()]

    with patch.object(
        loader, "_open_scenario_wms", side_effect=[False, True]
    ) as open_wms:
        loader.open_scenario_wms_batch(requests)

    assert open_wms.call_count == 2
    communication.bar_info.assert_called_once_with("Opened WMS for 1 of 2 scenario(s).")


def test_open_scenario_wms_reports_missing_descriptor():
    loader, communication = make_loader()
    request = scenario_wms_request().__class__(
        project={"id": "project", "name": "Project"},
        file_item={"id": "scenario", "data_type": "scenario"},
    )

    loader.open_scenario_wms(request)

    communication.bar_error.assert_called_once_with("Scenario descriptor is missing.")


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


def test_open_scenario_results_rejects_second_action_while_busy():
    loader, communication = make_loader()
    request = scenario_request()
    loader.begin_scenario_action(1)

    with patch.object(loader, "resolve_scenario_results") as resolve:
        loader.open_scenario_results(request)

    resolve.assert_not_called()
    communication.show_warn.assert_called_once_with(
        "A scenario result download is already in progress. "
        "Please wait for it to finish before opening another."
    )


def test_resolve_scenario_results_releases_gate_for_missing_descriptor():
    loader, communication = make_loader()
    loader.begin_scenario_action(1)
    request = scenario_request()
    request.file_item.pop("descriptor_id")

    loader.resolve_scenario_results(request, MagicMock())

    assert loader.scenario_action_busy is False
    assert loader.scenario_action_pending == 0
    communication.bar_error.assert_called_once_with("Scenario descriptor is missing.")


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


def test_open_items_does_not_dispatch_scenarios_when_busy():
    loader, communication = make_loader()
    request = scenario_request()
    loader.begin_scenario_action(1)

    with patch.object(loader, "open_scenario_results_batch") as open_batch:
        loader.open_items([request])

    open_batch.assert_not_called()
    communication.show_warn.assert_called_once()


def test_begin_scenario_action_uses_message_bar_for_batch_warning():
    loader, communication = make_loader()
    loader.begin_scenario_action(2)

    assert loader.begin_scenario_action(2) is False

    communication.bar_warn.assert_called_once_with(
        "A scenario download is still in process, no new scenario downloads "
        "will be added to the queue"
    )


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
    loader.begin_scenario_action(1)
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
        patch(
            "rana_qgis_plugin.loader.open_scenario_results_in_results_analysis"
        ) as open_results,
    ):
        loader.submit_scenario_result_download(request, [MagicMock()])

    termination_callback = task.taskTerminated.connect.call_args.args[0]
    termination_callback()
    open_results.assert_not_called()
    communication.bar_error.assert_called_once_with(
        "Scenario results download failed for: results.zip"
    )
    assert loader.scenario_action_busy is False


def test_scenario_download_completion_opens_results_analysis_once(tmp_path):
    loader, _ = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.dockwidget.isVisible.return_value = True
    file_item = {"id": "folder/result.zip"}

    with patch(
        "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            file_item,
            loader.communication,
        )

    results_analysis.load_result.assert_called_once_with(
        Path(tmp_path) / "results_3di.nc",
        Path(tmp_path) / "gridadmin.h5",
        group_path=["Project", "files", "folder", "result.zip"],
    )


def test_scenario_download_task_completion_queues_results_analysis(tmp_path):
    loader, _ = make_loader()
    loader.begin_scenario_action(1)
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
        patch.object(loader, "enqueue_results_analysis_open") as enqueue,
    ):
        loader.submit_scenario_result_download(request, [downloader])
        assert task.taskCompleted.connect.call_count == 1
        completion_callback = task.taskCompleted.connect.call_args_list[0].args[0]
        completion_callback()
        enqueue.assert_called_once_with(
            str(tmp_path),
            request.project,
            request.file_item,
        )
        task_manager.addTask.assert_called_once_with(task)


def test_results_analysis_queue_drains_in_order():
    loader, _ = make_loader()
    loader.begin_scenario_action(2)
    opened = []

    with (
        patch.object(loader, "set_progress_bar_busy"),
        patch(
            "rana_qgis_plugin.loader.open_scenario_results_in_results_analysis",
            side_effect=lambda target_dir, project, file_item, communication: (
                opened.append(file_item["id"])
            ),
        ),
    ):
        loader.enqueue_results_analysis_open("one", {}, {"id": "one"})
        loader.enqueue_results_analysis_open("two", {}, {"id": "two"})

    assert opened == ["one", "two"]
    assert loader.scenario_action_busy is False
    assert loader.results_analysis_queue == []


def test_results_analysis_queue_does_not_reenter():
    loader, _ = make_loader()
    loader.begin_scenario_action(2)
    active = 0
    max_active = 0
    enqueued = False

    def open_result(*args):
        nonlocal active, enqueued, max_active
        active += 1
        max_active = max(max_active, active)
        if not enqueued:
            enqueued = True
            loader.enqueue_results_analysis_open("two", {}, {"id": "two"})
        active -= 1

    with (
        patch.object(loader, "set_progress_bar_busy"),
        patch(
            "rana_qgis_plugin.loader.open_scenario_results_in_results_analysis",
            side_effect=open_result,
        ),
    ):
        loader.enqueue_results_analysis_open("one", {}, {"id": "one"})

    assert max_active == 1
    assert loader.scenario_action_busy is False


def test_results_analysis_queue_continues_after_failure():
    loader, communication = make_loader()
    loader.begin_scenario_action(2)
    opened = []

    def open_result(target_dir, project, file_item, communication):
        if target_dir == "one":
            raise RuntimeError("broken")
        opened.append(target_dir)

    with (
        patch.object(loader, "set_progress_bar_busy"),
        patch(
            "rana_qgis_plugin.loader.open_scenario_results_in_results_analysis",
            side_effect=open_result,
        ),
    ):
        loader.enqueue_results_analysis_open("one", {}, {"id": "one"})
        loader.enqueue_results_analysis_open("two", {}, {"id": "two"})

    assert opened == ["two"]
    communication.bar_error.assert_called_once_with(
        "Could not open scenario results: broken"
    )
    assert loader.scenario_action_busy is False


def test_raw_scenario_download_completion_reports_not_openable(tmp_path):
    loader, communication = make_loader()
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
        patch(
            "rana_qgis_plugin.loader.open_scenario_results_in_results_analysis"
        ) as open_results,
    ):
        loader.submit_scenario_result_download(
            request, [downloader], can_open_in_results_analysis=False
        )

    completion_callback = task.taskCompleted.connect.call_args_list[0].args[0]
    completion_callback()

    open_results.assert_not_called()
    communication.show_info.assert_called_once_with(
        "This is not a Rana simulation result and cannot be opened "
        "in Rana Results Analysis."
    )


def test_scenario_download_warns_when_results_analysis_is_missing(tmp_path):
    loader, communication = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()

    with patch(
        "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
        return_value=None,
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            {"id": "path/to/scenario"},
            communication,
        )

    communication.bar_warn.assert_called_once()


def test_scenario_download_falls_back_for_old_results_analysis_signature(tmp_path):
    loader, communication = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.dockwidget.isVisible.return_value = True
    results_analysis.load_result.side_effect = [
        TypeError("unexpected keyword argument 'group_path'"),
        None,
    ]

    with patch(
        "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            {"id": "path/to/scenario"},
            communication,
        )

    assert results_analysis.load_result.call_count == 2
    communication.bar_warn.assert_not_called()


def test_scenario_results_falls_back_to_two_argument_signature(tmp_path):
    loader, communication = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.dockwidget.isVisible.return_value = True
    results_analysis.load_result.side_effect = [
        TypeError("unexpected keyword argument 'group_path'"),
        TypeError("unexpected keyword argument 'project'"),
        None,
    ]

    with patch(
        "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            {"id": "path/to/scenario"},
            communication,
        )

    assert results_analysis.load_result.call_count == 3
    communication.bar_warn.assert_called_once()


def test_scenario_results_reraises_unrelated_type_error(tmp_path):
    loader, _ = make_loader()
    (tmp_path / "results_3di.nc").touch()
    (tmp_path / "gridadmin.h5").touch()
    results_analysis = MagicMock()
    results_analysis.load_result.side_effect = TypeError("invalid result data")

    with (
        patch(
            "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
            return_value=results_analysis,
        ),
        pytest.raises(TypeError, match="invalid result data"),
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            {"id": "path/to/scenario"},
            loader.communication,
        )


def test_scenario_results_skips_missing_files(tmp_path):
    loader, _ = make_loader()
    results_analysis = MagicMock()

    with patch(
        "rana_qgis_plugin.layer_management.layer_manager.get_threedi_results_analysis_tool_instance",
        return_value=results_analysis,
    ):
        open_scenario_results_in_results_analysis(
            str(tmp_path),
            {"name": "Project"},
            {"id": "path/to/scenario"},
            loader.communication,
        )

    results_analysis.load_result.assert_not_called()


def scenario_wms_request() -> OpenScenarioWmsRequest:
    return OpenScenarioWmsRequest(
        project={"id": "project", "name": "Project", "slug": "project"},
        file_item={
            "id": "path/to/scenario",
            "descriptor_id": "descriptor",
            "data_type": "scenario",
        },
    )


def scenario_descriptor(simulation: dict, scenario_id: int | None = 1) -> dict:
    return {
        "data_type": "scenario",
        "status": {"id": "completed"},
        "meta": {
            "id": scenario_id,
            "simulation": simulation,
            "grid": {
                "x": {"cell_size": 10},
                "crs": "EPSG:4326",
            },
        },
    }


def linked_descriptor() -> dict:
    descriptor = scenario_descriptor({"id": 42, "name": "Simulation"})
    descriptor["meta"]["schematisation"] = {
        "id": 7,
        "name": "Schematisation",
        "version": 3,
    }
    return descriptor
