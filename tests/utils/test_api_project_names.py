from rana_qgis_plugin.network_manager import NetworkUnavailableError
from rana_qgis_plugin.utils import api
from rana_qgis_plugin.utils.api import RanaFetchError, get_project_names


def fake_projects(monkeypatch, responses: dict):
    """Answer `get_tenant_project` from `responses`; exceptions in it are raised."""
    calls = []

    def get_tenant_project(project_id: str) -> dict:
        calls.append(project_id)
        response = responses[project_id]
        if isinstance(response, Exception):
            raise response
        return response

    monkeypatch.setattr(api, "get_tenant_project", get_tenant_project)
    return calls


def test_returns_the_name_per_project(monkeypatch):
    fake_projects(monkeypatch, {"p1": {"name": "Alpha"}, "p2": {"name": "Beta"}})

    assert get_project_names({"p1", "p2"}) == {"p1": "Alpha", "p2": "Beta"}


def test_leaves_out_projects_that_fail_or_have_no_name(monkeypatch):
    fake_projects(
        monkeypatch,
        {
            "p1": RanaFetchError("not found", "url", {}),
            "p2": {"name": "Beta"},
            "p3": {"slug": "no-name"},
        },
    )

    assert get_project_names(["p1", "p2", "p3"]) == {"p2": "Beta"}


def test_stops_asking_when_the_network_is_unavailable(monkeypatch):
    calls = fake_projects(
        monkeypatch,
        {
            "p1": NetworkUnavailableError("offline"),
            "p2": {"name": "Beta"},
        },
    )

    assert get_project_names(["p1", "p2"]) == {}
    assert calls == ["p1"]
