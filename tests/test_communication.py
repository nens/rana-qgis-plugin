from unittest.mock import MagicMock, patch

import pytest
from qgis.PyQt import sip
from qgis.PyQt.QtWidgets import QProgressBar, QTextBrowser, QWidget

from rana_qgis_plugin.communication import (
    finish_progress,
    update_step_progress,
)


@pytest.mark.parametrize(
    "step, step_pct, expected",
    [
        (0, 0, 0),
        (0, 50, 16),
        (0, 100, 33),
        (1, 0, 33),
        (1, 100, 66),
        (2, 0, 66),
        (2, 100, 100),
    ],
)
def test_update_step_progress_maps_steps_to_equal_segments(
    step_bar, step, step_pct, expected
):
    _, _, pb = step_bar
    update_step_progress(pb, step, step_pct)
    assert pb.value() == expected


def test_update_step_progress_sets_text(step_bar):
    _, _, pb = step_bar
    update_step_progress(pb, 1, 50, detail="Uploading: model.zip")
    assert (
        pb.parentWidget().findChild(QTextBrowser).toPlainText()
        == "Uploading: model.zip"
    )


def test_update_step_progress_without_detail_keeps_text(step_bar):
    _, _, pb = step_bar
    update_step_progress(pb, 2, 100)
    assert pb.parentWidget().findChild(QTextBrowser).toPlainText() == "Preparing"


def test_finish_progress_removes_the_items_widget(step_bar):
    iface, message_bar, pb = step_bar
    with patch.object(message_bar, "popWidget") as pop:
        finish_progress(iface, pb)
    pop.assert_called_once_with(pb.parentWidget())


def test_progress_helpers_log_instead_when_progress_item_is_dismissed(step_bar):
    iface, _, pb = step_bar
    sip.delete(pb)
    with patch("rana_qgis_plugin.communication.plugin_log_info") as log:
        update_step_progress(pb, 1, 50, detail="Uploading")
        finish_progress(iface, pb)
    assert [call.args[0] for call in log.call_args_list] == [
        "Progress item was dismissed: Uploading",
        "Progress item was dismissed before the process finished",
    ]


def test_progress_helpers_ignore_missing_progress_bar():
    iface = MagicMock()
    update_step_progress(None, 0, 50, detail="x")
    finish_progress(iface, None)
    iface.messageBar.assert_not_called()


def test_update_step_progress_without_text_browser_still_sets_value(
    qgis_application,
):
    container = QWidget()
    bar = QProgressBar(container)
    bar.setMaximum(100)
    update_step_progress(bar, 1, 0, detail="text")
    assert bar.value() == 33
