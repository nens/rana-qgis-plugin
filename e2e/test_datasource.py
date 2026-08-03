"""E2E tests for project listing in the QGIS Browser panel."""

import uuid

import pytest
from qgis.PyQt.QtTest import QTest

from rana_qgis_plugin.data_items.project_item import RanaProjectDataItem
from rana_qgis_plugin.utils.api import create_project, delete_project


@pytest.fixture
def authenticated(plugin, qtbot, qgis_application):
    """Ensure the QGIS auth manager has resolved the authcfg by performing one API call."""
    root = plugin.rana_root_item
    root.refresh()
    QTest.qWait(2000)
    qgis_application.processEvents()


@pytest.fixture
def rana_project(authenticated, plugin):
    result = create_project(
        {"code": f"e2e_{uuid.uuid4().hex[:24]}", "name": f"e2e_{uuid.uuid4().hex[:56]}"}
    )
    assert result is not None, "create_project failed — check authentication"
    yield result
    if result.get("id"):
        delete_project(result["id"])


def get_child_names(plugin, qgis_application):
    plugin.rana_root_item.refresh()
    QTest.qWait(3000)
    qgis_application.processEvents()
    return [
        child.name()
        for child in (plugin.rana_root_item.children() or [])
        if isinstance(child, RanaProjectDataItem)
    ]


def test_project_listing(plugin, qtbot, qgis_application, rana_project):
    # Step 1: project created by fixture — assert it appears after refresh
    qtbot.waitUntil(
        lambda: rana_project["name"] in get_child_names(plugin, qgis_application),
        timeout=30000,
    )

    # Step 2: delete project via API, refresh, assert it disappears
    delete_project(rana_project["id"])
    rana_project["id"] = None  # prevent double-delete in fixture teardown

    qtbot.waitUntil(
        lambda: rana_project["name"] not in get_child_names(plugin, qgis_application),
        timeout=30000,
    )
