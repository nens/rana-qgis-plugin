from unittest.mock import MagicMock

from qgis.core import QgsCoordinateReferenceSystem

from rana_qgis_plugin.widgets.new_wizard_pages.settings import (
    SchematisationSettingsPage,
)


def test_settings_page_rejects_unprojected_crs_and_zero_timestep(qgis_application):
    communication = MagicMock()
    page = SchematisationSettingsPage(communication, None)

    assert not page.validatePage()
    assert not page.settings_are_valid
    communication.show_warn.assert_called_once()
    warning = communication.show_warn.call_args.args[0]
    assert "projected coordinate system" in warning
    assert "Simulation timestep" in warning


def test_settings_page_accepts_projected_crs_and_collects_settings(qgis_application):
    communication = MagicMock()
    page = SchematisationSettingsPage(communication, None)
    widget = page.main_widget
    widget.crs.setCrs(QgsCoordinateReferenceSystem("EPSG:28992"))
    widget.time_step.setValue(300)
    widget.use_1d_flow_group.setChecked(False)
    widget.use_2d_flow_group.setChecked(False)

    assert page.validatePage(), communication.show_warn.call_args
    settings = widget.collect_new_schematisation_settings()

    assert settings["model_settings"]["epsg_code"] == 28992
    assert settings["model_settings"]["use_1d_flow"] == 0
    assert settings["model_settings"]["use_2d_flow"] == 0
    assert settings["time_step_settings"]["time_step"] == widget.time_step.value()
    assert settings["time_step_settings"]["output_time_step"] >= 300
    assert (
        settings["time_step_settings"]["output_time_step"]
        % settings["time_step_settings"]["time_step"]
        == 0
    )
    communication.show_warn.assert_not_called()


def test_settings_page_rejects_missing_conditional_dem(qgis_application, tmp_path):
    communication = MagicMock()
    page = SchematisationSettingsPage(communication, None)
    widget = page.main_widget
    widget.crs.setCrs(QgsCoordinateReferenceSystem("EPSG:28992"))
    widget.time_step.setValue(300)
    widget.use_2d_flow_group.setChecked(True)
    widget.minimum_cell_size.setValue(5)
    widget.friction_coefficient.setValue(0.03)
    missing_dem = tmp_path / "missing-dem.tif"
    widget.dem_file.setFilePath(str(missing_dem))

    assert not page.validatePage()
    assert "DEM" in communication.show_warn.call_args.args[0]
