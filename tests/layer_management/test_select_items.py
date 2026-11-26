from pathlib import Path

from rana_qgis_plugin.layer_management.layer_manager import RanaLayerRef
from rana_qgis_plugin.layer_management.sync_changes import file_key
from rana_qgis_plugin.layer_management.sync_prompt_dialog import select_items
from rana_qgis_plugin.utils.data_models import (
    DataType,
    StyleUploadItem,
    UploadableLayerItem,
)
from tests.layer_management.sync_prompt_helpers import FakeLayerSource


def make_style_item(descriptor_id: str, source: FakeLayerSource) -> StyleUploadItem:
    return StyleUploadItem(
        data_type=DataType.vector,
        local_file_path=f"{descriptor_id}.gpkg",
        file_ref_str=f"file {descriptor_id}.gpkg",
        upload_func=lambda files: None,
        project_id="project",
        descriptor_id=descriptor_id,
        layer_source=source,
    )


def make_data_item(descriptor_id: str) -> UploadableLayerItem:
    return UploadableLayerItem(
        RanaLayerRef("project", f"{descriptor_id}.gpkg", descriptor_id=descriptor_id),
        Path(f"{descriptor_id}.gpkg"),
        descriptor_id,
        "project",
    )


def test_select_items_returns_selected_items_and_discards_unselected_styles():
    kept_source = FakeLayerSource()
    dropped_source = FakeLayerSource()
    kept_style = make_style_item("kept", kept_source)
    dropped_style = make_style_item("dropped", dropped_source)
    kept_data = make_data_item("kept")
    dropped_data = make_data_item("dropped")

    style_to_sync, data_to_sync = select_items(
        [kept_style, dropped_style],
        [kept_data, dropped_data],
        {file_key("project", "kept", None)},
        {file_key("project", "kept", "kept.gpkg")},
    )

    assert style_to_sync == [kept_style]
    assert data_to_sync == [kept_data]
    assert not kept_source.discarded
    assert dropped_source.discarded


def test_select_items_discards_all_styles_when_none_selected():
    source = FakeLayerSource()
    style = make_style_item("only", source)
    data = make_data_item("only")

    style_to_sync, data_to_sync = select_items([style], [data], set(), set())

    assert style_to_sync == []
    assert data_to_sync == []
    assert source.discarded
