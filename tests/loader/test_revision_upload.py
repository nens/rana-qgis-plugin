from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from qgis.PyQt.QtCore import QCoreApplication, QEvent
from qgis.PyQt.QtWidgets import QDialog, QTextBrowser

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.communication import UICommunication
from rana_qgis_plugin.loader import Loader
from rana_qgis_plugin.simulation.workers import SchematisationUploadTask
from rana_qgis_plugin.utils.api import RanaFetchError

PROJECT = {"id": "project", "name": "Project"}


@pytest.fixture
def message_bar_loader(step_bar):
    """A loader whose progress items are pushed to a real message bar."""
    iface, message_bar, _ = step_bar
    message_bar.clearWidgets()
    communication = MagicMock()
    communication.iface = iface
    communication.progress_bar.side_effect = UICommunication(iface=iface).progress_bar
    return Loader(communication), communication, message_bar


def make_task():
    return SchematisationUploadTask(
        MagicMock(),
        MagicMock(),
        {
            "schematisation": SimpleNamespace(id=1, name="Model"),
            "latest_revision": SimpleNamespace(id=7, number=3),
            "cb_inherit_templates": False,
        },
    )


def wire(loader, task, error_signals=None, project=PROJECT):
    loader.wire_revision_upload(
        task, "project", 1, "Model", error_signals or ApiErrorSignals(), project
    )


def item_texts(message_bar):
    return [item.findChild(QTextBrowser).toPlainText() for item in message_bar.items()]


def test_upload_progress_updates_a_single_item(message_bar_loader):
    loader, _, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    task.progress_changed.emit("UPLOAD DEM", 50, 0, 50)
    task.progress_changed.emit("MAKE MODEL", 0, 50, 50)

    assert item_texts(message_bar) == ["Waiting for model checker"]


def test_upload_without_model_reports_uploaded_revision(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    task.upload_succeeded.emit(3)

    assert message_bar.items() == []
    communication.bar_info.assert_called_once_with("Revision 3 uploaded.")


def test_cancelled_upload_removes_item_and_warns(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    task.cancel()

    assert message_bar.items() == []
    communication.bar_warn.assert_called_once_with("Revision upload cancelled.")
    communication.bar_error.assert_not_called()


def test_failure_before_commit_reports_failed_upload(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    task.error_message = "boom"
    task.taskTerminated.emit()

    assert message_bar.items() == []
    communication.bar_error.assert_called_once_with("Revision upload failed: boom")


def test_failure_after_commit_reports_revision_without_model(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    task.revision_committed.emit(3)
    task.error_message = "Model checker failed"
    task.taskTerminated.emit()

    assert message_bar.items() == []
    communication.bar_error.assert_called_once_with(
        "Revision 3 was uploaded, but no model was created: Model checker failed"
    )


@pytest.mark.parametrize("ending", ["completed", "terminated"])
def test_upload_lock_is_released_when_task_ends(message_bar_loader, ending):
    loader, _, _ = message_bar_loader
    task = make_task()
    loader._revision_uploads_in_progress.add(1)
    wire(loader, task)

    getattr(task, f"task{ending.capitalize()}").emit()

    assert not loader.is_revision_upload_in_progress(1)


def test_model_hand_off_points_to_processes_with_given_project(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    error_signals = ApiErrorSignals()
    wire(loader, task, error_signals)

    with (
        patch.object(
            loader, "start_model_tracker_process", return_value={"job_id": "job-9"}
        ) as start,
        patch("rana_qgis_plugin.loader.get_tenant_project") as get_project,
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        task.model_requested.emit()
        task.progress_changed.emit("MAKE MODEL", 100, 50, 50)
        task.upload_succeeded.emit(3)

    start.assert_called_once_with("project", 1, "Model", 7, False)
    get_project.assert_not_called()
    assert point_user.call_args.args[:4] == (
        PROJECT,
        ["job-9"],
        error_signals,
        communication.iface.mainWindow(),
    )
    assert "Model" in point_user.call_args.kwargs["question"]
    assert message_bar.items() == []
    communication.bar_info.assert_not_called()


def test_model_hand_off_fetches_project_when_not_given(message_bar_loader):
    loader, _, _ = message_bar_loader
    task = make_task()
    wire(loader, task, project=None)

    with (
        patch.object(
            loader, "start_model_tracker_process", return_value={"id": "job-9"}
        ),
        patch(
            "rana_qgis_plugin.loader.get_tenant_project", return_value=PROJECT
        ) as get_project,
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        task.model_requested.emit()

    get_project.assert_called_once_with("project")
    assert point_user.call_args.args[:2] == (PROJECT, ["job-9"])


@pytest.mark.parametrize(
    "response, project_lookup",
    [
        pytest.param(
            {"job_id": "job-9"},
            {"side_effect": RanaFetchError("down", "url", {})},
            id="project-unavailable",
        ),
        pytest.param({}, {"return_value": PROJECT}, id="no-job-id"),
    ],
)
def test_model_hand_off_without_job_or_project_shows_info(
    message_bar_loader, response, project_lookup
):
    loader, communication, _ = message_bar_loader
    task = make_task()
    wire(loader, task, project=None)

    with (
        patch.object(loader, "start_model_tracker_process", return_value=response),
        patch("rana_qgis_plugin.loader.get_tenant_project", **project_lookup),
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        task.model_requested.emit()

    point_user.assert_not_called()
    communication.bar_info.assert_called_once_with(
        "Model creation started. See the Processes panel for progress."
    )


def test_model_hand_off_without_tracker_response_stays_silent(message_bar_loader):
    loader, communication, message_bar = message_bar_loader
    task = make_task()
    wire(loader, task)

    with (
        patch.object(loader, "start_model_tracker_process", return_value=None),
        patch.object(loader, "point_user_to_processes") as point_user,
    ):
        task.model_requested.emit()

    assert message_bar.items() == []
    point_user.assert_not_called()
    communication.bar_info.assert_not_called()


def test_cancelled_upload_wizard_leaves_no_item_and_logs_nothing(
    message_bar_loader,
):
    loader, _, message_bar = message_bar_loader
    tc = MagicMock()
    tc.fetch_schematisation.return_value = SimpleNamespace(
        id=1, name="Model", owner="org"
    )
    tc.fetch_organisations.return_value = [SimpleNamespace(unique_id="org")]
    wizard = MagicMock()

    def exec_wizard():
        # A modal dialog runs the event loop, which performs deferred deletes.
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        return QDialog.DialogCode.Rejected

    wizard.exec.side_effect = exec_wizard

    with (
        patch("rana_qgis_plugin.loader.get_threedi_api", return_value=object()),
        patch("rana_qgis_plugin.loader.ThreediCalls", return_value=tc),
        patch("rana_qgis_plugin.loader.hcc_working_dir", return_value="/tmp"),
        patch("rana_qgis_plugin.loader.LocalSchematisation"),
        patch("rana_qgis_plugin.loader.UploadWizard", return_value=wizard),
        patch("rana_qgis_plugin.communication.plugin_log_info") as log,
    ):
        result = loader.save_revision(
            "project", 1, 2, "/tmp/schema.gpkg", None, ApiErrorSignals()
        )

    assert result is None
    assert message_bar.items() == []
    log.assert_not_called()
