import pytest

from rana_qgis_plugin.layer_management.sync_changes import SyncChanges, SyncKind
from rana_qgis_plugin.layer_management.sync_summary import (
    build_details,
    build_summary,
    build_sync_notice,
)
from tests.layer_management.sync_prompt_helpers import fk


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
    assert build_summary(SyncChanges(data_files, style_files)) == expected


LIST = '<ul style="margin-top:0px; margin-bottom:0px">'


def header(text: str, top: str = "0px") -> str:
    return f'<p style="margin-top:{top}; margin-bottom:0px"><b>{text}</b></p>'


def test_build_details_single_layer_is_inline():
    assert build_details(SyncChanges({}, {fk("b.gpkg"): ["l3"]})) == (
        header("Style changes:") + LIST + "<li>project: b.gpkg: l3</li></ul>"
    )


def test_build_details_multiple_layers_are_nested_list():
    assert build_details(SyncChanges({fk("a.gpkg"): ["l1", "l2"]}, {})) == (
        header("Data changes:")
        + LIST
        + '<li>project: a.gpkg:<ul style="margin-top:0px; margin-bottom:0px">'
        + "<li>l1</li><li>l2</li></ul></li></ul>"
    )


def test_build_details_both_sections_with_file_in_both():
    assert build_details(
        SyncChanges({fk("a.gpkg"): ["l1"]}, {fk("a.gpkg"): ["l1"]})
    ) == (
        header("Data changes:")
        + LIST
        + "<li>project: a.gpkg: l1</li></ul>"
        + header("Style changes:", top="10px")
        + LIST
        + "<li>project: a.gpkg: l1</li></ul>"
    )


def test_build_details_escapes_names():
    assert build_details(SyncChanges({fk("a<b>.gpkg"): ["x&y"]}, {})) == (
        header("Data changes:")
        + LIST
        + "<li>project: a&lt;b&gt;.gpkg: x&amp;y</li></ul>"
    )


def test_build_details_lists_many_layers_without_truncation():
    layers = [f"layer{i}" for i in range(25)]
    details = build_details(SyncChanges({fk("a.gpkg"): layers}, {}))
    assert details.count("<li>layer") == 25
    assert details.endswith("<li>layer24</li></ul></li></ul>")


def test_sync_notice_for_single_file_names_only_data():
    assert build_sync_notice(
        SyncKind.DATA, SyncChanges(data={fk("roads.gpkg"): ["roads"]})
    ) == ("Syncing data of <b>project: roads.gpkg</b> to Rana...")


def test_sync_notice_for_single_file_names_only_style():
    assert build_sync_notice(
        SyncKind.STYLE, SyncChanges(style={fk("roads.gpkg"): ["roads"]})
    ) == ("Syncing style of <b>project: roads.gpkg</b> to Rana...")


def test_sync_notice_for_several_files_gives_the_count():
    files = {fk(f"f{i:02d}.gpkg"): ["layer"] for i in range(11)}
    assert (
        build_sync_notice(SyncKind.STYLE, SyncChanges(style=files))
        == "Syncing style of 11 files to Rana..."
    )


def test_sync_notice_escapes_names():
    assert build_sync_notice(
        SyncKind.DATA, SyncChanges(data={fk("roads<&>.gpkg"): ["roads"]})
    ) == ("Syncing data of <b>project: roads&lt;&amp;&gt;.gpkg</b> to Rana...")


def test_file_labels_include_the_project():
    changes = SyncChanges(
        data={fk("a.gpkg", "p1"): ["l1"], fk("a.gpkg", "p2"): ["l2"]},
        style={fk("b.gpkg", "p1"): ["l3"]},
    )

    details = build_details(changes)

    assert "<li>p1: a.gpkg: l1</li>" in details
    assert "<li>p2: a.gpkg: l2</li>" in details
    assert "<li>p1: b.gpkg: l3</li>" in details
    assert (
        build_summary(changes) == "3 files have unsynced changes (data: 2, style: 1)."
    )
