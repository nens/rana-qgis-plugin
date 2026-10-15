import pytest

from rana_qgis_plugin.simulation.utils import handle_csv_header


@pytest.mark.parametrize(
    "header",
    [["id", "timeseries"], ["timeseries", "id"]],
)
def test_handle_csv_header_accepts_supported_columns(header):
    assert handle_csv_header(header) is None


def test_handle_csv_header_rejects_unexpected_columns():
    header = ["id", "type", "connection_node_id", "timeseries"]

    assert handle_csv_header(header) == (
        "Unexpected column(s) in boundary conditions CSV: "
        "connection_node_id, type. Only 'id' and 'timeseries' columns are supported."
    )
