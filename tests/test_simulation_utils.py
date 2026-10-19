import pytest

from rana_qgis_plugin.simulation.utils import handle_csv_header


def test_handle_csv_header_accepts_supported_columns():
    assert handle_csv_header(["id", "timeseries"]) is None
    assert handle_csv_header(["timeseries", "id"]) is None


def test_handle_csv_header_rejects_unexpected_columns():
    header = ["id", "type", "connection_node_id", "timeseries"]

    error = handle_csv_header(header)
    assert error is not None
    assert "connection_node_id" in error
    assert "type" in error
