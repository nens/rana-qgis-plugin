from unittest.mock import patch

from qgis.PyQt.QtWidgets import QMessageBox

from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenScenarioRequest,
    OpenSchematisationRequest,
    OpenVectorFileRequest,
    VectorLayerRef,
    VectorTableRef,
)

from .helpers import make_loader, scenario_request


def test_open_items_dispatches_mixed_requests_by_type():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    scenario = OpenScenarioRequest(
        project, {"id": "scenario.json", "descriptor_id": "scenario-descriptor"}
    )
    vector = OpenFileRequest(project, {"id": "roads.gpkg", "data_type": "vector"})
    schematisation = OpenSchematisationRequest(
        project,
        {"id": "model.sqlite", "data_type": "threedi_schematisation"},
    )

    with (
        patch.object(loader, "open_scenario_results_batch") as open_scenario,
        patch.object(loader, "download_and_open_file") as open_file,
        patch.object(loader, "resolve_schematisation") as resolve_schematisation,
    ):
        loader.open_items([scenario, vector, schematisation])

    open_scenario.assert_called_once_with(scenario)
    open_file.assert_called_once_with(vector)
    resolve_schematisation.assert_called_once_with(schematisation)


def test_open_items_dispatches_selected_vector_children():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    request = OpenVectorFileRequest(
        project,
        file_item,
        (
            VectorLayerRef("roads", "roads-id"),
            VectorLayerRef("buildings", "buildings-id"),
        ),
    )

    with patch.object(loader, "download_and_open_vector_file") as open_vector_file:
        loader.open_items([request])

    open_vector_file.assert_called_once()
    aggregated = open_vector_file.call_args.args[0]
    assert isinstance(aggregated, OpenVectorFileRequest)
    assert aggregated == request


def test_open_items_file_request_subsumes_selected_children_request():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    file_request = OpenFileRequest(project, file_item)
    vector_request = OpenVectorFileRequest(
        project, file_item, (VectorLayerRef("roads", "roads-id"),)
    )

    with (
        patch.object(loader, "download_and_open_file") as open_file,
        patch.object(loader, "download_and_open_vector_file") as open_vector_file,
    ):
        loader.open_items([vector_request, file_request])

    open_file.assert_called_once_with(file_request)
    open_vector_file.assert_not_called()

    with (
        patch.object(loader, "download_and_open_file") as open_file,
        patch.object(loader, "download_and_open_vector_file") as open_vector_file,
    ):
        loader.open_items([file_request, vector_request])

    open_file.assert_called_once_with(file_request)
    open_vector_file.assert_not_called()


def test_open_items_merges_selected_children_for_same_file():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    layer_request = OpenVectorFileRequest(
        project, file_item, (VectorLayerRef("roads", "roads-id"),)
    )
    table_request = OpenVectorFileRequest(
        project, file_item, (VectorTableRef("attributes", "table-id"),)
    )

    with patch.object(loader, "download_and_open_vector_file") as open_vector_file:
        loader.open_items([layer_request, table_request])

    open_vector_file.assert_called_once_with(
        OpenVectorFileRequest(
            project,
            file_item,
            (
                VectorLayerRef("roads", "roads-id"),
                VectorTableRef("attributes", "table-id"),
            ),
        )
    )


def test_open_items_limits_unique_download_files():
    loader, communication = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    requests = [
        OpenVectorFileRequest(
            project,
            {"id": f"roads-{index}.gpkg", "data_type": "vector"},
            (VectorLayerRef(f"layer-{index}", str(index)),),
        )
        for index in range(11)
    ]
    with (
        patch(
            "rana_qgis_plugin.loader.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ),
        patch.object(loader, "download_and_open_vector_file") as open_vector_file,
    ):
        loader.open_items(requests)

    assert open_vector_file.call_count == 0
    communication.bar_error.assert_not_called()


def test_download_and_open_vector_file_opens_each_child_from_one_download():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    request = OpenVectorFileRequest(
        project,
        file_item,
        (
            VectorLayerRef("roads", "roads-id"),
            VectorTableRef("attributes", "attributes-id"),
        ),
    )

    with (
        patch.object(loader, "download_and_open") as download,
        patch.object(loader, "open_layer") as open_layer,
        patch.object(loader, "open_table") as open_table,
    ):
        loader.download_and_open_vector_file(request)
        callback = download.call_args.args[1]
        callback("/cache/roads.gpkg", project, file_item)

        download.assert_called_once()
        assert download.call_args.args[0] == request
    assert open_layer.call_args_list == [
        (("/cache/roads.gpkg", project, file_item, "roads", "roads-id"),),
    ]
    open_table.assert_called_once_with(
        "/cache/roads.gpkg", project, file_item, "attributes", "attributes-id"
    )


def test_resolve_folder_includes_scenarios_with_other_openable_files():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    files = [
        {"id": "scenario.json", "data_type": "scenario", "descriptor_id": "d1"},
        {"id": "roads.gpkg", "data_type": "vector", "descriptor_id": "d2"},
        {"id": "dem.tif", "data_type": "raster", "descriptor_id": "d3"},
    ]

    with patch("rana_qgis_plugin.loader.get_tenant_project_files", return_value=files):
        requests = loader._resolve_folder(project, "files")

    assert isinstance(requests[0], OpenScenarioRequest)
    assert [request.file_item["id"] for request in requests] == [
        "scenario.json",
        "roads.gpkg",
        "dem.tif",
    ]
