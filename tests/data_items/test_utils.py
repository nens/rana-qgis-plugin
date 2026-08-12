from unittest.mock import MagicMock, patch

import pytest

from rana_qgis_plugin.data_items.utils import get_loader_from_parent


def test_get_loader_from_parent_raises_for_none_parent():
    with pytest.raises(RuntimeError):
        get_loader_from_parent(None)


def test_get_loader_from_parent_raises_for_parent_without_loader():
    parent = MagicMock()
    del parent.loader
    with pytest.raises(AttributeError):
        get_loader_from_parent(parent)


def test_get_loader_from_parent():
    parent = MagicMock()
    loader = MagicMock()
    parent.loader = loader
    assert get_loader_from_parent(parent) == loader
