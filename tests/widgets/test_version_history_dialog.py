import pytest

from rana_qgis_plugin.widgets.version_history_dialog import get_model_state


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
