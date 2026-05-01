"""Tests for select-all header checkbox in FilesBrowser."""

from unittest.mock import MagicMock

from qgis.PyQt.QtCore import Qt
from qgis.PyQt.QtGui import QStandardItem

from rana_qgis_plugin.widgets.files_browser import FilesBrowser


def make_files_browser(qtbot):
    communication = MagicMock()
    from rana_qgis_plugin.widgets.utils_file_action import FileActionSignals

    file_signals = FileActionSignals()
    browser = FilesBrowser(communication, file_signals)
    qtbot.addWidget(browser)
    # Enable select mode; block signals to avoid style-related segfaults from
    # _checkbox_column_width() when no window handle exists yet.
    browser.select_btn.blockSignals(True)
    browser.select_btn.setChecked(True)
    browser.select_btn.blockSignals(False)
    browser.files_tv.setColumnHidden(0, False)
    browser.btn_stack.setCurrentIndex(1)
    return browser


def _add_file_row(browser, file_id="f1", name="file.txt"):
    checkbox_item = QStandardItem()
    checkbox_item.setCheckable(True)
    checkbox_item.setCheckState(Qt.CheckState.Unchecked)
    checkbox_item.setFlags(
        Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled
    )
    name_item = QStandardItem(name)
    name_item.setData({"id": file_id, "name": name, "type": "file"}, Qt.ItemDataRole.UserRole)
    browser.files_model.appendRow([checkbox_item, name_item])
    return checkbox_item


def test_header_checkbox_starts_unchecked(qtbot):
    browser = make_files_browser(qtbot)
    assert browser.files_tv.header().check_state() == Qt.CheckState.Unchecked


def test_clicking_header_checks_all_rows(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb2 = _add_file_row(browser, "f2", "b.txt")

    browser._on_header_check_state_changed(Qt.CheckState.Checked)

    assert cb1.checkState() == Qt.CheckState.Checked
    assert cb2.checkState() == Qt.CheckState.Checked


def test_clicking_header_unchecks_all_rows(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb1.setCheckState(Qt.CheckState.Checked)

    browser._on_header_check_state_changed(Qt.CheckState.Unchecked)

    assert cb1.checkState() == Qt.CheckState.Unchecked


def test_all_checked_syncs_header_to_checked(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb2 = _add_file_row(browser, "f2", "b.txt")
    cb1.setCheckState(Qt.CheckState.Checked)
    cb2.setCheckState(Qt.CheckState.Checked)

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.Checked


def test_some_checked_syncs_header_to_partial(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    _add_file_row(browser, "f2", "b.txt")
    cb1.setCheckState(Qt.CheckState.Checked)

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.PartiallyChecked


def test_none_checked_syncs_header_to_unchecked(qtbot):
    browser = make_files_browser(qtbot)
    _add_file_row(browser, "f1", "a.txt")

    browser._sync_header_checkbox()

    assert browser.files_tv.header().check_state() == Qt.CheckState.Unchecked


def test_header_check_all_enables_batch_buttons(qtbot):
    browser = make_files_browser(qtbot)
    _add_file_row(browser, "f1", "a.txt")

    browser._on_header_check_state_changed(Qt.CheckState.Checked)

    assert browser.btn_download_selected.isEnabled()
    assert browser.btn_delete_selected.isEnabled()


def test_header_uncheck_all_disables_batch_buttons(qtbot):
    browser = make_files_browser(qtbot)
    cb1 = _add_file_row(browser, "f1", "a.txt")
    cb1.setCheckState(Qt.CheckState.Checked)

    browser._on_header_check_state_changed(Qt.CheckState.Unchecked)

    assert not browser.btn_download_selected.isEnabled()
    assert not browser.btn_delete_selected.isEnabled()
