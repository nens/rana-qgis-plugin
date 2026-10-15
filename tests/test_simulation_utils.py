import pytest

from rana_qgis_plugin.simulation.utils import handle_csv_header


def test_handle_csv_header_accepts_supported_columns():
    header = [["id", "timeseries"], ["timeseries", "id"]]

    assert handle_csv_header(h) is None


def test_handle_csv_header_rejects_unexpected_columns():
    header = ["id", "type", "connection_node_id", "timeseries"]

    assert handle_csv_header(header) == (
        "Unexpected column(s) in boundary conditions CSV: "
        "connection_node_id, type. Only 'id' and 'timeseries' columns are supported."
    )
