from unittest.mock import patch

from rana_qgis_plugin.utils.data_models import (
    OpenFileRequest,
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
