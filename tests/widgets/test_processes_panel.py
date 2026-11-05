from dataclasses import replace
from typing import cast
from unittest.mock import MagicMock, call, patch

import pytest
from qgis.PyQt.QtCore import QItemSelectionModel, QPersistentModelIndex, QRect, Qt
from qgis.PyQt.QtWidgets import (
    QHeaderView,
    QLabel,
    QMessageBox,
    QStyleOptionViewItem,
    QTextEdit,
    QToolButton,
)

from rana_qgis_plugin.api_error_signals import ApiErrorSignals
from rana_qgis_plugin.utils.api import RanaFetchError
from rana_qgis_plugin.widgets.jobs_models import JobData
from rana_qgis_plugin.widgets.processes_panel import (
    JobsTableModel,
    ProcessesPanel,
    ProcessProgressBar,
    apply_job_progress,
)
from rana_qgis_plugin.widgets.utils_delegates import WordWrapDelegate
from rana_qgis_plugin.widgets.version_history_dialog import (
    SchematisationRevisionHistoryDialog,
)
from rana_qgis_plugin.workers.history import HistoryRow
from rana_qgis_plugin.workers.rana_jobs import JobsFetchTask
from tests.loader.helpers import make_loader


@pytest.fixture(autouse=True)
def simulation_tracker_process_id():
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_process_id_for_tag",
        return_value="tracker",
    ):
        yield


def make_job(job_id: int, name: str, progress: int = 0) -> JobData:
    return JobData(
        id=job_id,
        name=name,
        user={"id": "user-1", "given_name": "Test", "family_name": "User"},
        created=f"2026-10-29T12:0{job_id}:00Z",
        status="running",
        progress=progress,
        max_progress=100,
        process_id="tracker",
        process_name="Simulation tracker",
        inputs={},
    )


@pytest.fixture
def loader():
    loader, _communication = make_loader()
    return loader


def test_jobs_table_model_inserts_updates_and_removes_rows(qgis_application):
    model = JobsTableModel()
    resets = []
    model.modelReset.connect(lambda: resets.append(True))
    job_a = make_job(1, "A")
    job_b = make_job(2, "B")

    model.update_jobs([job_a, job_b])
    assert model.rowCount() == 2
    assert {model.job_at(row).id for row in range(model.rowCount())} == {1, 2}
    assert model.data(model.index(0, 0), Qt.ItemDataRole.UserRole).name in {"A", "B"}

    updated_b = make_job(2, "B", progress=50)
    model.update_jobs([updated_b, job_a])
    assert model.rowCount() == 2
    assert model.job_for_id(2) == updated_b

    model.update_jobs([updated_b])
    assert model.rowCount() == 1
    assert model.job_at(0).id == 2
    assert resets == []


def test_jobs_table_model_preserves_persistent_index_when_rows_insert(qgis_application):
    model = JobsTableModel()
    selected_job = make_job(1, "selected")
    model.update_jobs([selected_job])
    selected_index = QPersistentModelIndex(model.index(0, 0))

    model.update_jobs([make_job(2, "new"), selected_job])

    assert selected_index.isValid()
    assert model.data(selected_index, Qt.ItemDataRole.UserRole).id == selected_job.id


def test_jobs_table_model_follows_api_order_and_preserves_index(qgis_application):
    model = JobsTableModel()
    first = make_job(1, "Job 1")
    second = make_job(2, "Job 2")
    third = make_job(3, "Job 3")
    model.update_jobs([first, second, third])
    selected_index = QPersistentModelIndex(model.index(1, 0))

    model.update_jobs([third, first, second])

    assert [model.job_at(row).id for row in range(model.rowCount())] == [3, 1, 2]
    assert selected_index.isValid()
    assert model.data(selected_index, Qt.ItemDataRole.UserRole).id == 2
    assert selected_index.row() == 2


def test_jobs_table_model_highlights_and_clears_rows(qgis_application):
    model = JobsTableModel()
    model.update_jobs([make_job(1, "First"), make_job(2, "Second")])
    highlighted = model.index(1, 0)
    normal = model.index(0, 0)

    assert model.data(highlighted, Qt.ItemDataRole.BackgroundRole) is None
    model.set_highlighted_job_ids({2})
    assert model.data(highlighted, Qt.ItemDataRole.BackgroundRole) is not None
    assert model.data(normal, Qt.ItemDataRole.BackgroundRole) is None

    model.clear_highlighted_job_ids()
    assert model.data(highlighted, Qt.ItemDataRole.BackgroundRole) is None
    assert model.highlighted_job_ids() == set()


def test_process_progress_bar_maps_job_status_to_colors(qgis_application):
    progress_bar = ProcessProgressBar()

    for status in ("scheduled", "pending", "paused", "cancelling", "running"):
        progress_bar.set_status(status)
        assert progress_bar.styleSheet() == (
            f"QProgressBar::chunk {{ background-color: {progress_bar.COLOR_RUNNING}; }}"
        )

    progress_bar.set_status("completed")
    assert progress_bar.styleSheet() == (
        f"QProgressBar::chunk {{ background-color: {progress_bar.COLOR_FINISHED}; }}"
    )

    with patch.object(progress_bar, "set_failed") as set_failed:
        progress_bar.set_status("crashed")

    set_failed.assert_called_once_with()


def test_apply_job_progress_sets_value_range_format_and_status(qgis_application):
    progress_bar = ProcessProgressBar()
    job = make_job(1, "Simulation", 40)

    apply_job_progress(progress_bar, job)

    assert progress_bar.value() == 40
    assert progress_bar.maximum() == 100
    assert progress_bar.format() == "running (40%)"


def test_word_wrap_delegate_sizes_name_from_display_text(qgis_application):
    model = JobsTableModel()
    model.update_jobs([make_job(1, "A very long process name that needs wrapping")])
    delegate = WordWrapDelegate()
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 100, 20)

    size = delegate.sizeHint(option, model.index(0, 0))

    assert size.width() == 100
    assert size.height() > option.fontMetrics.height()


def test_processes_panel_builds_filter_params_and_keeps_stable_combo(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    filters = {"name": "rain", "who": "user-1", "status": "running"}

    assert panel._api_filters(filters) == {
        "search": "rain",
        "created_by": "user-1",
        "status": "running",
    }
    assert panel._api_filters({"name": "", "who": None, "status": None}) == {}


def test_processes_panel_debounces_refresh_until_active_fetch_completes(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel._visible = True
    panel._current_task = JobsFetchTask("project-1")

    panel._on_filters_changed({"name": "first", "who": None, "status": None})
    panel._on_filters_changed({"name": "latest", "who": None, "status": None})

    assert panel._filters == {"search": "latest"}
    assert panel._fetch_requested


def test_processes_panel_uses_flexible_text_columns_and_single_avatar(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    job = make_job(1, "A long job name")
    panel.model.update_jobs([job])

    header = panel.table.header()
    assert header is not None
    assert not panel.table.wordWrap()
    assert header.sectionResizeMode(0) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(1) == QHeaderView.ResizeMode.Stretch
    assert header.sectionResizeMode(2) == QHeaderView.ResizeMode.Fixed
    assert header.sectionResizeMode(3) == QHeaderView.ResizeMode.ResizeToContents
    assert header.sectionResizeMode(4) == QHeaderView.ResizeMode.Fixed
    assert panel.table.columnWidth(4) == 200
    assert panel.table.textElideMode() == Qt.TextElideMode.ElideRight
    assert panel.table.uniformRowHeights()
    assert panel.model.data(panel.model.index(0, 0), Qt.ItemDataRole.DisplayRole) == ""
    assert panel.model.data(panel.model.index(0, 2), Qt.ItemDataRole.DisplayRole) == ""
    assert panel.model.data(panel.model.index(0, 4), Qt.ItemDataRole.DisplayRole) == ""

    name_label = panel.table.indexWidget(panel.model.index(0, 0))
    assert isinstance(name_label, QLabel)
    assert not name_label.wordWrap()

    avatar_label = panel.table.indexWidget(panel.model.index(0, 2))
    assert isinstance(avatar_label, QLabel)
    assert not avatar_label.autoFillBackground()
    assert not avatar_label.pixmap().isNull()
    assert avatar_label.toolTip() == job.user_name


def test_processes_panel_shows_cancel_only_for_eligible_simulation_jobs(
    qgis_application, loader
):
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_process_id_for_tag",
        return_value="tracker",
    ):
        panel = ProcessesPanel(
            {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
        )
    eligible = make_job(1, "Eligible")
    eligible.inputs["simulation_id"] = 42
    other_process = replace(make_job(2, "Other process"), process_id="other")
    no_simulation = replace(make_job(3, "No simulation"), inputs={})
    panel.model.update_jobs([eligible, other_process, no_simulation])

    cancel_buttons = []
    progress_widths = []
    for row in range(panel.model.rowCount()):
        status_widget = panel.table.indexWidget(panel.model.index(row, 4))
        assert status_widget is not None
        button = status_widget.findChild(QToolButton)
        assert button is not None
        cancel_buttons.append(button)
        progress_bar = status_widget.findChild(ProcessProgressBar)
        assert progress_bar is not None
        progress_widths.append(progress_bar.width())

    assert [button.isHidden() for button in cancel_buttons] == [False, True, True]
    assert progress_widths == [160, 160, 160]
    assert panel.table.columnWidth(4) >= 160 + 4 + 24


def test_cancel_simulation_confirmation_and_success_update_status(
    qgis_application, loader
):
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_process_id_for_tag",
        return_value="tracker",
    ):
        panel = ProcessesPanel(
            {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
        )
    job = make_job(1, "Simulation")
    job.inputs["simulation_id"] = 42
    panel.model.update_jobs([job])
    panel._update_all_row_widgets()

    with (
        patch(
            "rana_qgis_plugin.widgets.processes_panel.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ) as confirm,
        patch("rana_qgis_plugin.widgets.processes_panel.get_threedi_api") as get_api,
        patch("rana_qgis_plugin.widgets.processes_panel.ThreediCalls") as calls,
    ):
        panel._cancel_simulation(job.id)

    confirm.assert_called_once()
    calls.assert_called_once_with(get_api.return_value)
    calls.return_value.create_simulation_action.assert_called_once_with(
        42, name="shutdown"
    )
    updated_job = panel.model.job_for_id(job.id)
    assert updated_job is not None
    assert updated_job.status == "cancelling"
    status_widget = panel.table.indexWidget(panel.model.index(0, 4))
    assert status_widget is not None
    button = status_widget.findChild(QToolButton)
    assert button is not None
    assert button.isHidden()


def test_cancel_simulation_decline_sends_no_action(qgis_application, loader):
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_process_id_for_tag",
        return_value="tracker",
    ):
        panel = ProcessesPanel(
            {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
        )
    job = make_job(1, "Simulation")
    job.inputs["simulation_id"] = 42
    panel.model.update_jobs([job])

    with (
        patch(
            "rana_qgis_plugin.widgets.processes_panel.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ),
        patch("rana_qgis_plugin.widgets.processes_panel.ThreediCalls") as calls,
    ):
        panel._cancel_simulation(job.id)

    calls.assert_not_called()
    unchanged_job = panel.model.job_for_id(job.id)
    assert unchanged_job is not None
    assert unchanged_job.status == "running"


def test_cancel_simulation_failure_reports_error_and_reenables_button(
    qgis_application, loader
):
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_process_id_for_tag",
        return_value="tracker",
    ):
        panel = ProcessesPanel(
            {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
        )
    job = make_job(1, "Simulation")
    job.inputs["simulation_id"] = 42
    panel.model.update_jobs([job])
    panel._update_all_row_widgets()
    errors = []
    panel.error_signals.fetch_error_occurred.connect(
        lambda message, _show_dialog: errors.append(message)
    )

    with (
        patch(
            "rana_qgis_plugin.widgets.processes_panel.QMessageBox.question",
            return_value=QMessageBox.StandardButton.Yes,
        ),
        patch(
            "rana_qgis_plugin.widgets.processes_panel.ThreediCalls",
            side_effect=RuntimeError("shutdown failed"),
        ),
        patch("rana_qgis_plugin.widgets.processes_panel.get_threedi_api"),
    ):
        panel._cancel_simulation(job.id)

    status_widget = panel.table.indexWidget(panel.model.index(0, 4))
    assert status_widget is not None
    button = status_widget.findChild(QToolButton)
    assert button is not None
    assert button.isEnabled()
    unchanged_job = panel.model.job_for_id(job.id)
    assert unchanged_job is not None
    assert unchanged_job.status == "running"
    assert errors == ["shutdown failed"]


def test_highlight_jobs_fetches_then_selects_and_highlights_matching_rows(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel._visible = True
    fetched_jobs = [
        {
            "id": 1,
            "name": "First",
            "creator": {
                "id": "user-1",
                "given_name": "Test",
                "family_name": "User",
            },
            "created_at": "2026-10-29T12:01:00Z",
            "state": {"type": "running", "progress": 0.1},
            "process": {"id": "tracker", "name": "Simulation tracker"},
            "inputs": {},
        },
        {
            "id": 2,
            "name": "Started job",
            "creator": {
                "id": "user-1",
                "given_name": "Test",
                "family_name": "User",
            },
            "created_at": "2026-10-29T12:02:00Z",
            "state": {"type": "running", "progress": 0.3},
            "process": {"id": "tracker", "name": "Simulation tracker"},
            "inputs": {},
        },
    ]
    task = JobsFetchTask("project-1")
    task.result = {"items": fetched_jobs[:1]}
    panel._current_task = task

    with patch.object(panel, "_request_fetch") as request_fetch:
        panel.highlight_jobs(["2"])

    assert panel._highlight_job_ids == {"2"}
    assert not panel._fetch_requested
    request_fetch.assert_not_called()

    with patch.object(panel, "_request_fetch"):
        panel._fetch_completed(task)

    assert panel._highlight_job_ids == {"2"}
    assert panel.model.highlighted_job_ids() == set()

    followup_task = JobsFetchTask("project-1")
    followup_task.result = {"items": fetched_jobs}
    panel._current_task = followup_task
    with patch.object(panel, "_request_fetch"):
        panel._fetch_completed(followup_task)

    selection_model = panel.table.selectionModel()
    assert selection_model is not None
    selected_rows = {index.row() for index in selection_model.selectedRows()}
    assert selected_rows == {1}
    assert panel.model.highlighted_job_ids() == {2}
    assert panel._highlight_timer.isActive()

    panel._highlight_timer.stop()


def test_fetch_completed_keeps_valid_jobs_when_one_item_is_malformed(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel._visible = True
    errors = []
    panel.error_signals.fetch_error_occurred.connect(
        lambda message, _show_dialog: errors.append(message)
    )
    valid_job = make_job(1, "Valid")
    malformed_item = {"id": 2, "name": "Broken"}
    task = JobsFetchTask("project-1")
    task.result = {
        "items": [
            {
                "id": valid_job.id,
                "name": valid_job.name,
                "creator": {
                    "id": "user-1",
                    "given_name": "Test",
                    "family_name": "User",
                },
                "created_at": "2026-10-29T12:01:00Z",
                "state": {"type": "running", "progress": 0.1},
                "process": {"id": "tracker", "name": "Simulation tracker"},
                "inputs": {},
            },
            malformed_item,
        ]
    }
    panel._current_task = task

    with patch.object(panel, "_request_fetch"):
        panel._fetch_completed(task)

    assert panel.model.job_for_id(valid_job.id) is not None
    assert panel.model.rowCount() == 1
    assert len(errors) == 1
    assert errors[0].startswith("Could not read job 2 from Rana:")


def test_model_start_notifies_with_returned_job_id_and_signals():
    dialog = MagicMock(spec=SchematisationRevisionHistoryDialog)
    dialog.project = {"id": "project-id"}
    dialog.error_signals = ApiErrorSignals()
    dialog.loader = MagicMock()
    dialog.loader.start_model_tracker_process.return_value = {"job_id": "job-42"}
    button = MagicMock()
    row = HistoryRow(
        values=[],
        metadata={
            "schematisation_id": 1,
            "schematisation_name": "Schematisation",
            "revision_id": 2,
        },
    )

    SchematisationRevisionHistoryDialog.create_model(dialog, row, button)

    dialog.loader.point_user_to_processes.assert_called_once_with(
        dialog.project, ["job-42"], dialog.error_signals, dialog
    )
    assert button.setEnabled.call_args_list == [call(False), call(False)]


def test_selected_job_logs_show_timestamp_level_message_and_exception(
    qgis_application, loader
):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job with logs")])
    logs_response = {
        "items": [
            {
                "timestamp": "2026-10-29T12:00:00Z",
                "log_level": 40,
                "message": "Simulation failed",
                "exception": {
                    "title": "Invalid model",
                    "traceback": "line 1\nline 2",
                    "error_type": "user",
                    "description": None,
                },
            }
        ]
    }
    selection_model = panel.table.selectionModel()
    assert selection_model is not None

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value=logs_response,
    ) as fetch_logs:
        selection_model.select(
            panel.model.index(0, 0),
            cast(
                QItemSelectionModel.SelectionFlags,
                QItemSelectionModel.SelectionFlag.Select
                | QItemSelectionModel.SelectionFlag.Rows,
            ),
        )

    assert isinstance(panel.logs, QTextEdit)
    panel.logs.setPlaceholderText("")
    assert panel.logs.toPlainText() == (
        "2026-10-29T12:00:00Z | 40 | Simulation failed\n"
        "Exception: Invalid model\nline 1\nline 2"
    )
    fetch_logs.assert_called_once_with("1")


def test_stale_logs_response_does_not_replace_new_selection(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "First"), make_job(2, "Second")])
    selection_model = panel.table.selectionModel()
    assert selection_model is not None
    selection_model.select(
        panel.model.index(0, 0),
        cast(
            QItemSelectionModel.SelectionFlags,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        ),
    )
    response = {
        "items": [
            {
                "timestamp": "first response",
                "log_level": 20,
                "message": "first job logs",
            }
        ]
    }

    def select_another_job(*_args, **_kwargs):
        selection_model.blockSignals(True)
        try:
            selection_model.clearSelection()
            selection_model.select(
                panel.model.index(1, 0),
                cast(
                    QItemSelectionModel.SelectionFlags,
                    QItemSelectionModel.SelectionFlag.Select
                    | QItemSelectionModel.SelectionFlag.Rows,
                ),
            )
        finally:
            selection_model.blockSignals(False)
        return response

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        side_effect=select_another_job,
    ):
        panel._refresh_selected_job_logs()

    assert panel.logs.toPlainText() == ""


def test_logs_clear_when_no_job_is_selected(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.logs.setPlainText("previous job logs")
    panel.model.update_jobs([make_job(1, "No selection")])

    with patch("rana_qgis_plugin.widgets.processes_panel.get_job_logs") as fetch_logs:
        panel._refresh_selected_job_logs()

    assert panel.logs.toPlainText() == ""
    assert panel.logs.placeholderText() == "Select a job to view its logs."
    fetch_logs.assert_not_called()


def test_selected_job_without_logs_shows_empty_state(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Empty logs")])
    selection_model = panel.table.selectionModel()
    assert selection_model is not None
    selection_model.select(
        panel.model.index(0, 0),
        cast(
            QItemSelectionModel.SelectionFlags,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        ),
    )

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value={"items": []},
    ):
        panel._refresh_selected_job_logs()

    assert panel.logs.toPlainText() == ""
    assert panel.logs.placeholderText() == "No logs available for this job."


def test_selected_job_log_error_is_reported(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Failed logs")])
    selection_model = panel.table.selectionModel()
    assert selection_model is not None
    selection_model.select(
        panel.model.index(0, 0),
        cast(
            QItemSelectionModel.SelectionFlags,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        ),
    )
    errors = []
    panel.error_signals.fetch_error_occurred.connect(
        lambda message, show_dialog: errors.append((message, show_dialog))
    )

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        side_effect=RanaFetchError("logs unavailable", "url", {}),
    ):
        panel._refresh_selected_job_logs()

    assert panel.logs.placeholderText() == "Could not load job logs."
    assert errors == [("logs unavailable. URL: url. params: {}", False)]


def select_first_row(panel):
    selection_model = panel.table.selectionModel()
    assert selection_model is not None
    selection_model.select(
        panel.model.index(0, 0),
        cast(
            QItemSelectionModel.SelectionFlags,
            QItemSelectionModel.SelectionFlag.Select
            | QItemSelectionModel.SelectionFlag.Rows,
        ),
    )
    return selection_model


def test_log_box_is_hidden_until_a_job_is_selected(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job")])

    assert panel._log_box.isHidden()
    assert panel._log_box.isCollapsed()


def test_selecting_a_job_opens_log_with_hide_label(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job")])

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value={"items": []},
    ):
        select_first_row(panel)

    assert not panel._log_box.isHidden()
    assert not panel._log_box.isCollapsed()
    assert panel._log_box.title() == "Hide log"


def test_collapsing_log_switches_label_to_show(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job")])
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value={"items": []},
    ):
        select_first_row(panel)

    panel._log_box.findChild(QToolButton, "collapseButton").click()
    panel.show()
    assert panel._log_box.isCollapsed()
    assert panel._log_box.title() == "Show log"


def test_clearing_selection_hides_and_collapses_log_box(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job")])
    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value={"items": []},
    ):
        selection_model = select_first_row(panel)
        selection_model.clearSelection()

    assert panel._log_box.isHidden()
    assert panel._log_box.isCollapsed()


def test_collapsed_log_does_not_fetch_logs(qgis_application, loader):
    panel = ProcessesPanel(
        {"id": "project-1", "slug": "project"}, ApiErrorSignals(), loader
    )
    panel.model.update_jobs([make_job(1, "Job")])
    select_first_row(panel)
    panel._log_box.setCollapsed(True)

    with patch(
        "rana_qgis_plugin.widgets.processes_panel.get_job_logs",
        return_value={"items": []},
    ) as fetch_logs:
        panel._refresh_selected_job_logs()

    fetch_logs.assert_not_called()
