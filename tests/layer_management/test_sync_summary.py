import pytest

from rana_qgis_plugin.layer_management.sync_summary import build_summary
from tests.layer_management.sync_prompt_helpers import fk, make_changes


@pytest.mark.parametrize(
    ("data_files", "style_files", "expected"),
    [
        (
            {fk("a.gpkg"): ["l1"], fk("b.gpkg"): ["l2"]},
            {},
            "2 files have unsynced changes (data: 2).",
        ),
        (
            {},
            {fk("a.gpkg"): ["l1"], fk("b.gpkg"): ["l2"], fk("c.gpkg"): ["l3"]},
            "3 files have unsynced changes (style: 3).",
        ),
        (
            {fk("a.gpkg"): ["l1"], fk("b.gpkg"): ["l2"]},
            {fk("a.gpkg"): ["l1"], fk("c.gpkg"): ["l3"]},
            "3 files have unsynced changes (data: 2, style: 2).",
        ),
        (
            {fk("a.gpkg"): ["l1"]},
            {},
            "1 file has unsynced changes (data).",
        ),
        (
            {},
            {fk("a.gpkg"): ["l1"]},
            "1 file has unsynced changes (style).",
        ),
        (
            {fk("a.gpkg"): ["l1"]},
            {fk("a.gpkg"): ["l1"]},
            "1 file has unsynced changes (data and style).",
        ),
    ],
)
def test_build_summary(data_files, style_files, expected):
    assert build_summary(make_changes(data_files, style_files)) == expected


def test_build_summary_counts_files_per_project_separately():
    changes = make_changes(
        {fk("a.gpkg", "p1"): ["l1"], fk("a.gpkg", "p2"): ["l2"]},
        {fk("b.gpkg", "p1"): ["l3"]},
    )

    assert (
        build_summary(changes) == "3 files have unsynced changes (data: 2, style: 1)."
    )


@pytest.mark.parametrize(
    ("data_files", "style_files", "expected"),
    [
        ({fk("a.gpkg"): ["l1"]}, {}, "1 file has unsynced changes."),
        ({}, {fk("a.gpkg"): ["l1"]}, "1 file has unsynced changes."),
        (
            {fk("a.gpkg"): ["l1"], fk("b.gpkg"): ["l2"]},
            {},
            "2 files have unsynced changes.",
        ),
    ],
)
def test_build_summary_without_kinds_only_counts_files(
    data_files, style_files, expected
):
    changes = make_changes(data_files, style_files)

    assert build_summary(changes, include_kinds=False) == expected
