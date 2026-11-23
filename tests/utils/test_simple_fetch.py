from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.utils import api


def make_network_manager(result, content=None, last_http_status=None):
    network_manager = MagicMock()
    network_manager.fetch.return_value = result
    network_manager.content = content
    network_manager.last_http_status = last_http_status
    return network_manager


def test_simple_fetch_returns_content_on_success():
    network_manager = make_network_manager((True, None), content={"ok": True})

    with (
        patch.object(api, "NetworkManager", return_value=network_manager),
        patch.object(api, "get_authcfg_id", return_value="cfg"),
    ):
        assert api.simple_fetch("https://example.com/x") == {"ok": True}


def test_simple_fetch_raises_on_redirect_instead_of_returning_none():
    network_manager = make_network_manager(
        (True, "https://s3.example.com/presigned"), last_http_status=302
    )

    with (
        patch.object(api, "NetworkManager", return_value=network_manager),
        patch.object(api, "get_authcfg_id", return_value="cfg"),
        pytest.raises(api.RanaFetchError, match="https://s3.example.com/presigned"),
    ):
        api.simple_fetch("https://example.com/x")
