from types import SimpleNamespace
from unittest.mock import patch

import pytest

from rana_qgis_plugin.widgets.schematisation_browser import SchematisationBrowser


@pytest.fixture
def selection_data():
    schematisation = SimpleNamespace(
        id=42,
        name="Test schematisation",
        last_updated="2026-10-09",
        created_by_first_name="Ada",
        created_by_last_name="Lovelace",
    )
    revisions = [
        SimpleNamespace(id=100, number=0, commit_date="2026-10-01", commit_message=""),
        SimpleNamespace(
            id=102,
            number=2,
            commit_date="2026-10-09",
            commit_message="Latest",
        ),
        SimpleNamespace(
            id=101,
            number=1,
            commit_date="2026-10-05",
            commit_message="Middle",
        ),
    ]
    return schematisation, revisions


def test_schematisation_browser_orders_revisions_and_selects_latest(
    qgis_application, selection_data
):
    schematisation, revisions = selection_data
    with patch("rana_qgis_plugin.widgets.schematisation_browser.ThreediCalls") as calls:
        calls.return_value.fetch_schematisation_revisions.return_value = revisions
        with patch(
            "rana_qgis_plugin.widgets.schematisation_browser.get_schematisations",
            return_value=[vars(schematisation)],
        ) as fetch_schematisations:
            browser = SchematisationBrowser(object())

    assert [
        browser.revisions_table.item(row, 0).text()
        for row in range(browser.revisions_table.rowCount())
    ] == ["2", "1", "0"]
    assert browser.selected_schematisation == vars(schematisation)
    assert browser.selected_revision is revisions[1]
    fetch_schematisations.assert_called_once_with("")
    calls.return_value.fetch_schematisation_revisions.assert_called_once_with(42)


def test_schematisation_table_sorts_names_case_insensitively(qgis_application):
    schematisations = [
        {
            "id": 1,
            "name": "zebra",
            "last_updated": "2026-10-01",
            "created_by_first_name": "",
            "created_by_last_name": "",
        },
        {
            "id": 2,
            "name": "Apple",
            "last_updated": "2026-10-02",
            "created_by_first_name": "",
            "created_by_last_name": "",
        },
    ]
    with patch("rana_qgis_plugin.widgets.schematisation_browser.ThreediCalls") as calls:
        calls.return_value.fetch_schematisation_revisions.return_value = []
        with patch(
            "rana_qgis_plugin.widgets.schematisation_browser.get_schematisations",
            return_value=schematisations,
        ):
            browser = SchematisationBrowser(object())
            browser.schematisation_table.sortItems(0)

    assert [browser.schematisation_table.item(row, 0).text() for row in range(2)] == [
        "Apple",
        "zebra",
    ]


def test_schematisation_browser_disables_confirmation_without_revisions(
    qgis_application,
):
    schematisation = {"id": 42, "name": "No revisions"}
    with patch("rana_qgis_plugin.widgets.schematisation_browser.ThreediCalls") as calls:
        calls.return_value.fetch_schematisation_revisions.return_value = []
        with patch(
            "rana_qgis_plugin.widgets.schematisation_browser.get_schematisations",
            return_value=[schematisation],
        ):
            browser = SchematisationBrowser(object())

    assert browser.revisions_table.rowCount() == 0
    assert not browser.ok_button.isEnabled()
    assert "no committed revisions" in browser.status_label.text().lower()


def test_schematisation_browser_shows_revision_fetch_error(qgis_application):
    schematisation = {"id": 42, "name": "Fetch failure"}
    with patch("rana_qgis_plugin.widgets.schematisation_browser.ThreediCalls") as calls:
        calls.return_value.fetch_schematisation_revisions.side_effect = RuntimeError(
            "HCC unavailable"
        )
        with patch(
            "rana_qgis_plugin.widgets.schematisation_browser.get_schematisations",
            return_value=[schematisation],
        ):
            browser = SchematisationBrowser(object())

    assert not browser.ok_button.isEnabled()
    assert "HCC unavailable" in browser.status_label.text()


def test_schematisation_browser_shows_schematisation_fetch_error(qgis_application):
    with patch("rana_qgis_plugin.widgets.schematisation_browser.ThreediCalls") as calls:
        with patch(
            "rana_qgis_plugin.widgets.schematisation_browser.get_schematisations",
            side_effect=RuntimeError("HCC unavailable"),
        ):
            browser = SchematisationBrowser(object())

    assert browser.schematisation_table.rowCount() == 0
    assert not browser.ok_button.isEnabled()
    assert "HCC unavailable" in browser.status_label.text()
