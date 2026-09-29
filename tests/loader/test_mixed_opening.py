from unittest.mock import patch

from qgis.PyQt.QtWidgets import QMessageBox

from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
    OpenLayersRequest,
    OpenScenarioRequest,
    OpenSchematisationRequest,
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


def test_open_items_dispatches_aggregated_layers():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    request = OpenLayersRequest(
        project,
        file_item,
        (("roads", "roads-id"), ("buildings", "buildings-id")),
    )

    with patch.object(loader, "download_and_open_layers") as open_layers:
        loader.open_items([request])

    open_layers.assert_called_once()
    aggregated = open_layers.call_args.args[0]
    assert isinstance(aggregated, OpenLayersRequest)
    assert aggregated == request


def test_open_items_file_request_subsumes_layer_request():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    file_request = OpenFileRequest(project, file_item)
    layer_request = OpenLayersRequest(project, file_item, (("roads", "roads-id"),))

    with (
        patch.object(loader, "download_and_open_file") as open_file,
        patch.object(loader, "download_and_open_layers") as open_layers,
    ):
        loader.open_items([layer_request, file_request])

    open_file.assert_called_once_with(file_request)
    open_layers.assert_not_called()

    with (
        patch.object(loader, "download_and_open_file") as open_file,
        patch.object(loader, "download_and_open_layers") as open_layers,
    ):
        loader.open_items([file_request, layer_request])

    open_file.assert_called_once_with(file_request)
    open_layers.assert_not_called()


def test_open_items_limits_unique_download_files():
    loader, communication = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    requests = [
        OpenLayersRequest(
            project,
            {"id": f"roads-{index}.gpkg", "data_type": "vector"},
            ((f"layer-{index}", str(index)),),
        )
        for index in range(11)
    ]
    with (
        patch(
            "rana_qgis_plugin.loader.QMessageBox.question",
            return_value=QMessageBox.StandardButton.No,
        ),
        patch.object(loader, "download_and_open_layers") as open_layers,
    ):
        loader.open_items(requests)

    assert open_layers.call_count == 0
    communication.bar_error.assert_not_called()


def test_download_and_open_layers_opens_each_layer_from_one_download():
    loader, _ = make_loader()
    project = {"id": "project", "name": "Project", "slug": "project"}
    file_item = {"id": "roads.gpkg", "data_type": "vector"}
    request = OpenLayersRequest(
        project,
        file_item,
        (
            ("roads", "roads-id"),
            ("buildings", "buildings-id"),
        ),
    )

    with (
        patch.object(loader, "download_and_open") as download,
        patch.object(loader, "open_layer") as open_layer,
    ):
        loader.download_and_open_layers(request)
        callback = download.call_args.args[1]
        callback("/cache/roads.gpkg", project, file_item)

        download.assert_called_once()
        assert download.call_args.args[0] == request
    assert open_layer.call_args_list == [
        (("/cache/roads.gpkg", project, file_item, "roads", "roads-id"),),
        (("/cache/roads.gpkg", project, file_item, "buildings", "buildings-id"),),
    ]


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
