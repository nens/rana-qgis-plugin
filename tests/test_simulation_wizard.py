from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.simulation.simulation_wizard import BoundaryConditionsWidget


def make_boundary_conditions_widget():
    communication = MagicMock()
    wizard = SimpleNamespace(communication=communication)
    parent_page = SimpleNamespace(parent_wizard=wizard)
    widget = SimpleNamespace(
        parent_page=parent_page,
        TYPE_1D=BoundaryConditionsWidget.TYPE_1D,
        TYPE_2D=BoundaryConditionsWidget.TYPE_2D,
        cb_interpolate_bc_1d=MagicMock(isChecked=MagicMock(return_value=False)),
        cb_interpolate_bc_2d=MagicMock(isChecked=MagicMock(return_value=False)),
    )
    return widget, communication


def test_boundary_conditions_invalid_upload_preserves_previous_state(tmp_path):
    csv_file = tmp_path / "boundary_conditions.csv"
    csv_file.write_text("id,type,timeseries\n1,1,\"0,1\"\n", encoding="utf-8")
    widget, communication = make_boundary_conditions_widget()
    previous_values = [{"id": 7}]
    widget.boundary_conditions_1d_timeseries = previous_values
    widget.file_bc_1d_upload = MagicMock()
    widget.open_upload_dialog = lambda boundary_conditions_type: (
        BoundaryConditionsWidget.open_upload_dialog(widget, boundary_conditions_type)
    )

    with (
        patch(
            "rana_qgis_plugin.simulation.simulation_wizard.QFileDialog.getOpenFileName",
            return_value=(str(csv_file), None),
        ),
        patch(
            "rana_qgis_plugin.simulation.simulation_wizard.read_3di_settings",
            return_value=str(tmp_path),
        ),
        patch("rana_qgis_plugin.simulation.simulation_wizard.save_3di_settings"),
    ):
        BoundaryConditionsWidget.load_csv(widget, BoundaryConditionsWidget.TYPE_1D)

    assert widget.boundary_conditions_1d_timeseries is previous_values
    widget.file_bc_1d_upload.setText.assert_not_called()
    communication.show_warn.assert_called_once()
