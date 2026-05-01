"""Tests for CheckableHeaderView."""

import pytest
from qgis.PyQt.QtCore import Qt

from rana_qgis_plugin.widgets.utils_view import CheckableHeaderView


@pytest.fixture
def header(qtbot):
    h = CheckableHeaderView(Qt.Orientation.Horizontal)
    h.setMinimumSectionSize(10)
    h.resize(200, 30)
    qtbot.addWidget(h)
    return h


def test_initial_check_state_is_unchecked(header):
    assert header.check_state() == Qt.CheckState.Unchecked


def test_set_check_state_checked(header):
    header.set_check_state(Qt.CheckState.Checked)
    assert header.check_state() == Qt.CheckState.Checked


def test_set_check_state_partial(header):
    header.set_check_state(Qt.CheckState.PartiallyChecked)
    assert header.check_state() == Qt.CheckState.PartiallyChecked


def test_set_check_state_unchecked(header):
    header.set_check_state(Qt.CheckState.Checked)
    header.set_check_state(Qt.CheckState.Unchecked)
    assert header.check_state() == Qt.CheckState.Unchecked


# Click interaction tests
# Mouse simulation on a headerless widget is unreliable in headless Qt tests
# (sectionViewportPosition returns -1 without a model/sections), so we test
# the click handler directly via _handle_checkbox_click().
# The mousePressEvent → _handle_checkbox_click() dispatch is a single-line call
# covered by manual UI testing.


def test_click_unchecked_becomes_checked(header):
    signals = []
    header.check_state_changed.connect(signals.append)
    header._handle_checkbox_click()
    assert header.check_state() == Qt.CheckState.Checked
    assert signals == [Qt.CheckState.Checked]


def test_click_checked_becomes_unchecked(header):
    header.set_check_state(Qt.CheckState.Checked)
    signals = []
    header.check_state_changed.connect(signals.append)
    header._handle_checkbox_click()
    assert header.check_state() == Qt.CheckState.Unchecked
    assert signals == [Qt.CheckState.Unchecked]


def test_click_partially_checked_becomes_checked(header):
    header.set_check_state(Qt.CheckState.PartiallyChecked)
    signals = []
    header.check_state_changed.connect(signals.append)
    header._handle_checkbox_click()
    assert header.check_state() == Qt.CheckState.Checked
    assert signals == [Qt.CheckState.Checked]
