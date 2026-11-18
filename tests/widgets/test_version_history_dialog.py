from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.widgets.version_history_dialog import (
    SchematisationRevisionHistoryDialog,
    get_model_state,
)


@pytest.mark.parametrize(
    ("revision_id", "model_ids", "generating_ids", "can_create_model", "expected"),
    [
        (1, {1}, set(), False, (True, False, True, "")),
        (1, set(), set(), True, (False, False, True, "")),
        (
            1,
            set(),
            set(),
            False,
            (
                False,
                False,
                False,
                "The maximum number of Rana models has been reached. "
                "Please delete one of the existing models before creating a new one.",
            ),
        ),
        (
            1,
            set(),
            {1},
            True,
            (
                False,
                True,
                False,
                "The Rana model for this revision is being generated. "
                "Click Refresh to update.",
            ),
        ),
    ],
)
def test_get_model_state(
    revision_id,
    model_ids,
    generating_ids,
    can_create_model,
    expected,
):
    state = get_model_state(revision_id, model_ids, generating_ids, can_create_model)

    assert (
        state["has_model"],
        state["is_generating"],
        state["model_enabled"],
        state["model_tooltip"],
    ) == expected


def test_generating_model_counts_once_for_schematisation_capacity():
    model_ids = {1}
    generating_ids = {1, 2}
    model_limit = 2

    can_create_model = len(model_ids | generating_ids) < model_limit

    assert not can_create_model
    assert not get_model_state(3, model_ids, generating_ids, can_create_model)[
        "model_enabled"
    ]


def test_fetch_page_adds_generating_state_to_revision_row():
    revision = SimpleNamespace(
        id=1,
        number=4,
        has_threedimodel=False,
        commit_date="2026-01-01T12:00:00Z",
        commit_first_name="Ada",
        commit_last_name="Lovelace",
        commit_user=None,
        commit_message="message",
    )
    calls = MagicMock()
    calls.fetch_schematisation_revisions.return_value = [revision]
    calls.fetch_generating_models.return_value = [SimpleNamespace(revision_id=1)]
    dialog = SchematisationRevisionHistoryDialog.__new__(
        SchematisationRevisionHistoryDialog
    )
    dialog.descriptor_id = "descriptor"

    with (
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.get_threedi_schematisation",
            return_value={
                "schematisation": {
                    "id": 9,
                    "name": "schema",
                    "threedimodel_limit": 2,
                },
                "management_url": "https://example.test",
            },
        ),
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.get_threedi_api",
            return_value=object(),
        ),
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.ThreediCalls",
            return_value=calls,
        ),
    ):
        rows, next_cursor = dialog.fetch_page(None)

    assert next_cursor is None
    assert rows[0].metadata["is_generating"] is True
    assert rows[0].metadata["model_enabled"] is False
    assert "being generated" in rows[0].metadata["model_tooltip"]


def test_fetch_page_propagates_generating_model_fetch_error():
    calls = MagicMock()
    calls.fetch_schematisation_revisions.return_value = []
    calls.fetch_generating_models.side_effect = RuntimeError("request failed")
    dialog = SchematisationRevisionHistoryDialog.__new__(
        SchematisationRevisionHistoryDialog
    )
    dialog.descriptor_id = "descriptor"

    with (
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.get_threedi_schematisation",
            return_value={"schematisation": {"id": 9, "threedimodel_limit": 2}},
        ),
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.get_threedi_api",
            return_value=object(),
        ),
        patch(
            "rana_qgis_plugin.widgets.version_history_dialog.ThreediCalls",
            return_value=calls,
        ),
    ):
        with pytest.raises(RuntimeError, match="request failed"):
            dialog.fetch_page(None)
