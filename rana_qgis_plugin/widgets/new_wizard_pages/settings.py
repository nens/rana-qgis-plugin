import os
from collections import defaultdict
from pathlib import Path

from qgis.core import QgsRasterLayer, QgsUnitTypes
from qgis.gui import QgsFileWidget, QgsProjectionSelectionWidget
from qgis.PyQt.QtCore import QSize
from qgis.PyQt.QtGui import QColor, QPalette
from qgis.PyQt.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QRadioButton,
    QSizePolicy,
    QSpacerItem,
    QSpinBox,
    QWidget,
    QWizardPage,
)

from rana_qgis_plugin.simulation.utils_ui import scan_widgets_parameters

HEADER_LAYOUT = """
QLabel {
    font-weight: bold;
    font-size: 18px;
}"""


class SchematisationSettingsPage(QWizardPage):
    """New schematisation settings definition page."""

    def __init__(self, communication, parent):
        super().__init__(parent)
        self.communication = communication
        self.main_widget = SchematisationSettingsWidget(self)
        self.settings_are_valid = False
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout = QGridLayout()
        layout.addWidget(self.main_widget)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def validatePage(self):
        """Overriding page validation logic."""
        warning_messages = []
        self.settings_are_valid = True
        # Check validity of CRS
        crs = self.main_widget.crs.crs()
        if (
            not crs.isValid()
            or crs.isGeographic()
            or crs.mapUnits() != QgsUnitTypes.DistanceMeters
        ):
            self.settings_are_valid = False
            warning_messages.append(
                "CRS must be a projected coordinate system using meters as units."
            )
        # Check non-zero settings
        non_zero_required_widgets = [
            ("Simulation timestep", self.main_widget.time_step),
        ]
        if self.main_widget.use_2d_flow_group.isChecked():
            non_zero_required_widgets.append(
                ("Computational Cell Size", self.main_widget.minimum_cell_size)
            )
            if not self.main_widget.friction_coefficient_file.filePath():
                non_zero_required_widgets.append(
                    (
                        "Global 2D friction coefficient",
                        self.main_widget.friction_coefficient,
                    )
                )
        invalid_zero_settings = []
        for setting_name, setting_widget in non_zero_required_widgets:
            if not setting_widget.value() > 0:
                invalid_zero_settings.append(setting_name)
        if invalid_zero_settings:
            self.settings_are_valid = False
            warn = "\n".join(
                f"'{setting_name}' value have to be greater than 0"
                for setting_name in invalid_zero_settings
            )
            warning_messages.append(warn)
        # Check the validity of the raster paths
        valid_path_required_widgets = []
        if self.main_widget.use_2d_flow_group.isChecked():
            if self.main_widget.dem_file.filePath():
                valid_path_required_widgets.append(("DEM", self.main_widget.dem_file))
            if self.main_widget.friction_coefficient.value() == 0.0:
                valid_path_required_widgets.append(
                    ("friction", self.main_widget.friction_coefficient_file)
                )
        invalid_path_settings = []
        for setting_name, setting_widget in valid_path_required_widgets:
            raster_filepath = Path(setting_widget.filePath())
            if not os.path.exists(
                raster_filepath
            ) or raster_filepath.suffix.lower() not in {".tif", ".tiff"}:
                invalid_path_settings.append(setting_name)
        if invalid_path_settings:
            self.settings_are_valid = False
            warn = "\n".join(
                f"Chosen {setting_name} file does not exist or is not a GeoTIFF (.tif or .tiff)"
                for setting_name in invalid_path_settings
            )
            warning_messages.append(warn)
        if warning_messages:
            self.communication.show_warn("\n".join(warning_messages), self, "Warning")
        return self.settings_are_valid


class SchematisationSettingsWidget(QWidget):
    """Widget for the Schematisation Settings page."""

    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()

        self.crs.setOptionVisible(QgsProjectionSelectionWidget.DefaultCrs, False)
        self.use_1d_flow_group.toggled.connect(self.on_1d_flow_toggled)
        self.use_2d_flow_group.toggled.connect(self.on_2d_flow_toggled)
        self.dem_file.fileChanged.connect(self.on_dem_file_change)

    def setup_ui(self):
        self.setWindowTitle("Setting")

        palette = QPalette()
        palette.setColor(QPalette.Button, QColor(255, 255, 255))
        self.setPalette(palette)

        main_layout = QGridLayout(self)

        header = QLabel("Schematisation settings")
        header.setStyleSheet(HEADER_LAYOUT)
        main_layout.addWidget(header, 0, 0)

        # Schematisation settings section
        self.schematisation_settings = QWidget()
        gridLayout_8 = QGridLayout(self.schematisation_settings)
        gridLayout_8.setContentsMargins(20, 0, 0, 0)

        crs_label = QLabel("Coordinate reference system:")
        crs_label.setToolTip("Your schematization's CRS. Must be a projected CRS.")
        crs_label.setMinimumSize(QSize(350, 0))
        self.crs = QgsProjectionSelectionWidget()
        self.crs.setMinimumSize(QSize(0, 25))
        self.crs.setToolTip(
            "Coordinate reference system that should be used to interpret your data."
        )
        self.crs.setObjectName("crs")

        crs_layout = QGridLayout()
        crs_layout.addWidget(crs_label, 1, 0)
        crs_layout.addWidget(self.crs, 1, 1)
        crs_widget = QWidget()
        crs_widget.setLayout(crs_layout)
        gridLayout_8.addWidget(crs_widget, 0, 0, 1, 1)

        # 2D Flow group (row 2)
        self.use_2d_flow_group = QGroupBox("2D Flow")
        self.use_2d_flow_group.setCheckable(True)
        self.use_2d_flow_group.setToolTip(
            "Check this box if you want to include surface flow (2D) in your schematisation"
        )
        self.use_2d_flow_group.setObjectName("use_2d_flow_group")
        grid2d = QGridLayout(self.use_2d_flow_group)

        # DEM file row
        lbl_dem = QLabel("Digital elevation model:")
        lbl_dem.setToolTip(
            "Raster file (.tif) that contains the elevation (m MSL) for each pixel"
        )

        self.dem_file = QgsFileWidget()
        self.dem_file.setToolTip(
            "Raster file (.tif) that contains the elevation (m MSL) for each pixel"
        )
        self.dem_file.setObjectName("dem_file")

        grid2d.addWidget(lbl_dem, 0, 0)
        grid2d.addWidget(self.dem_file, 0, 2, 1, 2)

        # Computational cell size
        lbl_cell = QLabel("Computational cell size [m]:")
        lbl_cell.setToolTip(
            "This value is used to fill in the 'minimum_cell_size' attribute in the model settings"
        )
        grid2d.addWidget(lbl_cell, 1, 0, 1, 2)

        self.minimum_cell_size = QDoubleSpinBox()
        self.minimum_cell_size.setMinimumSize(QSize(150, 25))
        self.minimum_cell_size.setButtonSymbols(self.minimum_cell_size.NoButtons)
        self.minimum_cell_size.setMinimum(0.0)
        self.minimum_cell_size.setMaximum(9999.0)
        self.minimum_cell_size.setValue(0.0)
        self.minimum_cell_size.setToolTip(
            "This value is used to fill in the 'minimum_cell_size' attribute in the model settings"
        )
        self.minimum_cell_size.setObjectName("minimum_cell_size")

        grid2d.addWidget(self.minimum_cell_size, 1, 2, 1, 2)

        self.friction_shallow_water_depth_correction_flat = QRadioButton("Flat")
        self.friction_shallow_water_depth_correction_flat.setChecked(True)
        self.friction_shallow_water_depth_correction_flat.setToolTip(
            "For sloping areas, the appropriate numerical limiters will be set"
        )
        self.friction_shallow_water_depth_correction_flat.setObjectName(
            "friction_shallow_water_depth_correction_flat"
        )
        self.friction_shallow_water_depth_correction_sloping = QRadioButton("Sloping")
        self.friction_shallow_water_depth_correction_sloping.setToolTip(
            "For sloping areas, the appropriate numerical limiters will be set"
        )
        self.friction_shallow_water_depth_correction_sloping.setObjectName(
            "friction_shallow_water_depth_correction_sloping"
        )

        label_5 = QLabel("The model area is predominantly:")
        label_5.setToolTip(
            "For sloping areas, the appropriate numerical limiters will be set"
        )
        grid2d.addWidget(label_5, 2, 0, 1, 2)
        hfr = QHBoxLayout()
        hfr.setContentsMargins(0, 0, 0, 0)
        hfr.addWidget(self.friction_shallow_water_depth_correction_flat)
        hfr.addWidget(self.friction_shallow_water_depth_correction_sloping)
        grid2d.addLayout(hfr, 2, 2, 1, 2)

        gridLayout_8.addWidget(self.use_2d_flow_group, 1, 0)

        # 1D Flow group (row 3)
        self.use_1d_flow_group = QGroupBox("1D Flow")
        self.use_1d_flow_group.setCheckable(True)
        self.use_1d_flow_group.setToolTip(
            "Check this box if you want to schematise open water or hydraulic structures as 1D elements and/or include sewerage"
        )
        grid1d = QGridLayout(self.use_1d_flow_group)
        self.use_1d_flow_group.setObjectName("use_1d_flow_group")

        self.manhole_aboveground_storage_area_label = QLabel(
            "Above-surface manhole storage area [m2]:"
        )
        self.manhole_aboveground_storage_area_label.setToolTip(
            "This option is only relevant for sewerage models without 2D flow"
        )
        self.manhole_aboveground_storage_area_label.setMinimumSize(QSize(350, 0))

        self.manhole_aboveground_storage_area = QSpinBox()
        self.manhole_aboveground_storage_area.setMinimumSize(QSize(150, 25))
        self.manhole_aboveground_storage_area.setMaximum(999999999)
        self.manhole_aboveground_storage_area.setToolTip(
            "This option is only relevant for sewerage models without 2D flow"
        )
        self.manhole_aboveground_storage_area.setObjectName(
            "manhole_aboveground_storage_area"
        )
        self.manhole_aboveground_storage_area.setEnabled(False)

        grid1d.addWidget(self.manhole_aboveground_storage_area_label, 0, 0)
        grid1d.addWidget(self.manhole_aboveground_storage_area, 0, 2, 1, 2)

        gridLayout_8.addWidget(self.use_1d_flow_group, 2, 0)

        # 0D inflow checkbox (row 4)
        self.use_0d_inflow_checkbox = QCheckBox("0D Inflow")
        self.use_0d_inflow_checkbox.setToolTip(
            "Check this box if you want to include rainfall-runoff from surfaces and/or urban wastewater production (dry weather flow)"
        )
        self.use_0d_inflow_checkbox.setObjectName("use_0d_inflow_checkbox")

        self.use_0d_inflow_checkbox.setChecked(False)
        gridLayout_8.addWidget(self.use_0d_inflow_checkbox, 3, 0)

        # Friction coefficients group (row 5)
        self.friction_coefficients_group = QGroupBox("Friction coefficients")
        gridF = QGridLayout(self.friction_coefficients_group)

        lbl_fric_type = QLabel("Friction type:")
        lbl_fric_type.setToolTip("Friction type")

        self.friction_type_text = QComboBox()
        self.friction_type_text.setToolTip("Friction type")
        self.friction_type_text.addItems(["1: Chezy", "2: Manning"])
        self.friction_type_text.setObjectName("friction_type_text")

        gridF.addWidget(lbl_fric_type, 0, 0)
        gridF.addWidget(self.friction_type_text, 0, 1, 1, 2)

        self.friction_coefficient_label = QLabel("Friction file:")
        self.friction_coefficient_label.setToolTip(
            "Raster (.tif) that contains a friction coefficient for each pixel"
        )

        self.friction_coefficient_file = QgsFileWidget()
        self.friction_coefficient_file.setMinimumSize(QSize(0, 25))
        self.friction_coefficient_file.setToolTip(
            "Raster (.tif) that contains a friction coefficient for each pixel"
        )
        self.friction_coefficient_file.setObjectName("friction_coefficient_file")

        gridF.addWidget(self.friction_coefficient_label, 2, 0)
        gridF.addWidget(self.friction_coefficient_file, 2, 1, 1, 2)

        lbl_fric_coeff = QLabel("Global 2D friction coefficient:")
        lbl_fric_coeff.setToolTip(
            "If you do not want to specify the friction value per pixel, use this option to set a global friction coefficient"
        )

        self.friction_coefficient = QDoubleSpinBox()
        self.friction_coefficient.setMinimumSize(QSize(150, 25))
        self.friction_coefficient.setButtonSymbols(self.friction_coefficient.NoButtons)
        self.friction_coefficient.setDecimals(4)
        self.friction_coefficient.setMaximum(1000.0)
        self.friction_coefficient.setToolTip(
            "If you do not want to specify the friction value per pixel, use this option to set a global friction coefficient"
        )
        self.friction_coefficient.setObjectName("friction_coefficient")

        gridF.addWidget(lbl_fric_coeff, 3, 0)
        gridF.addWidget(self.friction_coefficient, 3, 2)

        gridLayout_8.addWidget(self.friction_coefficients_group, 4, 0)
        main_layout.addWidget(self.schematisation_settings, 2, 0)

        # Simulation / time step settings
        self.simulation_settings = QWidget()
        self.simulation_settings_layout = QGridLayout(self.simulation_settings)
        header = QLabel("Time step settings")
        header.setStyleSheet(HEADER_LAYOUT)
        self.simulation_settings_layout.addWidget(header, 0, 0)

        widget_inner = QWidget()
        inner_layout = QGridLayout(widget_inner)

        lbl_sim_step = QLabel("Simulation time step [s]:")
        lbl_sim_step.setToolTip("Simulation time step [s]")
        inner_layout.addWidget(lbl_sim_step, 0, 0)

        self.time_step = QSpinBox()
        self.time_step.setMinimumSize(QSize(150, 25))
        self.time_step.setButtonSymbols(self.time_step.NoButtons)
        inner_layout.addWidget(self.time_step, 0, 2)
        self.time_step.setObjectName("time_step")

        lbl_duration = QLabel("Typical simulation duration:")
        lbl_duration.setToolTip("Used to set the output time step")
        inner_layout.addWidget(lbl_duration, 1, 0)

        self.output_time_step_text = QComboBox()
        self.output_time_step_text.setToolTip("Used to set the output time step")
        self.output_time_step_text.addItems(
            ["0-3 hours", "3-12 hours", "12-24 hours", "> 24 hours"]
        )
        self.output_time_step_text.setObjectName("output_time_step_text")
        inner_layout.addWidget(self.output_time_step_text, 1, 1, 1, 2)

        widget_inner.setLayout(inner_layout)
        self.simulation_settings_layout.addWidget(widget_inner, 1, 0)

        main_layout.addWidget(self.simulation_settings, 4, 0)

        spacer = QSpacerItem(20, 40, QSizePolicy.Minimum, QSizePolicy.Expanding)
        main_layout.addItem(spacer, 5, 0)

    def on_1d_flow_toggled(self, on):
        """Logic for checking/unchecking 1D Flow settings group."""
        if on:
            if self.use_2d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setDisabled(True)
                self.manhole_aboveground_storage_area.setDisabled(True)
            else:
                self.manhole_aboveground_storage_area_label.setEnabled(True)
                self.manhole_aboveground_storage_area.setEnabled(True)

    def on_2d_flow_toggled(self, on):
        """Logic for checking/unchecking 2D Flow settings group."""
        if on:
            self.friction_coefficient_label.setEnabled(True)
            self.friction_coefficient_file.setEnabled(True)
            self.minimum_cell_size.setValue(0.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setDisabled(True)
                self.manhole_aboveground_storage_area.setDisabled(True)
        else:
            self.friction_coefficient_label.setDisabled(True)
            self.friction_coefficient_file.setDisabled(True)
            self.minimum_cell_size.setValue(9999.0)
            if self.use_1d_flow_group.isChecked():
                self.manhole_aboveground_storage_area_label.setEnabled(True)
                self.manhole_aboveground_storage_area.setEnabled(True)

    def on_dem_file_change(self):
        """Extra logic for changing DEM file path."""
        dem_filepath = self.dem_file.filePath()
        raster_layer = QgsRasterLayer(dem_filepath)
        if raster_layer.isValid():
            raster_crs = raster_layer.crs()
            self.crs.setCrs(raster_crs)

    @property
    def model_settings_defaults(self):
        """Model settings defaults."""
        defaults = {
            "dem_file": None,
            "calculation_point_distance_1d": 1000.0,
            "embedded_cutoff_threshold": 0.05,
            "epsg_code": None,
            "friction_averaging": 0,
            "friction_coefficient": None,
            "friction_coefficient_file": None,
            "friction_type": None,
            "minimum_cell_size": 0.0,
            "use_groundwater_flow": None,
            "use_interflow": None,
            "nr_grid_levels": 1,
            "manhole_aboveground_storage_area": None,
            "max_angle_1d_advection": 1.570795,
            "maximum_table_step_size": None,
            "use_simple_infiltration": None,
            "minimum_table_step_size": 0.05,
            "table_step_size_1d": 0.01,
            "use_1d_flow": None,
            "use_2d_flow": None,
            "use_2d_rain": None,
            "node_open_water_detection": 0,
        }
        return defaults

    @property
    def numerical_settings_defaults(self):
        """Numerical settings defaults."""
        defaults = {
            "cfl_strictness_factor_1d": 1.0,
            "cfl_strictness_factor_2d": 1.0,
            "convergence_cg": 0.000000001,
            "convergence_eps": 0.00001,
            "flooding_threshold": 0.0001,
            "flow_direction_threshold": 0.000001,
            "friction_shallow_water_depth_correction": None,
            "general_numerical_threshold": 0.00000001,
            "time_integration_method": 0,
            "limiter_waterlevel_gradient_1d": 1,
            "limiter_waterlevel_gradient_2d": None,
            "limiter_slope_crossectional_area_2d": None,
            "limiter_slope_friction_2d": None,
            "max_degree_gauss_seidel": None,
            "max_non_linear_newton_iterations": 20,
            "min_friction_velocity": 0.005,
            "min_surface_area": 0.00000001,
            "use_preconditioner_cg": 1,
            "preissmann_slot": 0.0,
            "pump_implicit_ratio": 1.0,
            "limiter_slope_thin_water_layer": None,
            "use_of_cg": 20,
            "use_nested_newton": None,
        }
        return defaults

    @property
    def simulation_template_settings_defaults(self):
        """Simulation template settings defaults."""
        defaults = {
            "name": "default",
            "use_structure_control": None,
            "use_0d_inflow": None,
        }
        return defaults

    @property
    def time_step_settings_defaults(self):
        """Time step settings defaults."""
        defaults = {
            "time_step": None,
            "min_time_step": 0.01,
            "max_time_step": None,
            "output_time_step": None,
            "use_time_step_stretch": 0,
        }
        return defaults

    @property
    def physical_settings_defaults(self):
        """Physical settings defaults."""
        defaults = {
            "use_advection_1d": 3,
            "use_advection_2d": 1,
        }
        return defaults

    @property
    def initial_conditions_defaults(self):
        """Initial conditions defaults."""
        defaults = {
            "initial_groundwater_level": None,
            "initial_groundwater_level_file": None,
            "initial_groundwater_level_aggregation": None,
            "initial_water_level_aggregation": None,
            "initial_water_level": -99.0,
            "initial_water_level_file": None,
        }
        return defaults

    @property
    def interception_defaults(self):
        """Interception defaults."""
        defaults = {
            "interception": None,
            "interception_file": None,
        }
        return defaults

    @property
    def dry_weather_flow_distribution_defaults(self):
        defaults = {
            "description": "Kennisbank Stichting Rioned - https://www.riool.net/huishoudelijk-afvalwater",
            "distribution": "3,1.5,1,1,0.5,0.5,2.5,8,7.5,6,5.5,5,4.5,4,4,3.5,3.5,4,5.5,8,7,5.5,4.5,4",
        }
        return defaults

    @property
    def surface_parameters_defaults(self):
        return {
            "id": [
                "101",
                "102",
                "103",
                "104",
                "105",
                "106",
                "107",
                "108",
                "109",
                "110",
                "111",
                "112",
                "113",
                "114",
                "115",
            ],
            "description": [
                "gesloten verharding, hellend",
                "gesloten verharding, vlak",
                "gesloten verharding, vlak uitgestrekt",
                "open verharding, hellend",
                "open verharding, vlak",
                "open verharding, vlak uitgestrekt",
                "dak, hellend",
                "dak, vlak",
                "dak, vlak uitgestrekt",
                "onverhard, hellend",
                "onverhard, vlak",
                "onverhard, vlak uitgestrekt",
                "half verhard, hellend",
                "half verhard, vlak",
                "half verhard, vlak uitgestrekt",
            ],
            "outflow_delay": [
                "0.5",
                "0.2",
                "0.1",
                "0.5",
                "0.2",
                "0.1",
                "0.5",
                "0.2",
                "0.1",
                "0.5",
                "0.2",
                "0.1",
                "0.5",
                "0.2",
                "0.1",
            ],
            "surface_layer_thickness": [
                "0",
                "0.5",
                "1",
                "0",
                "0.5",
                "1",
                "0",
                "2",
                "4",
                "2",
                "4",
                "6",
                "2",
                "4",
                "6",
            ],
            "infiltration": [
                "0",
                "0",
                "0",
                "1",
                "1",
                "1",
                "0",
                "0",
                "0",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ],
            "max_infiltration_capacity": [
                "0",
                "0",
                "0",
                "2",
                "2",
                "2",
                "0",
                "0",
                "0",
                "5",
                "5",
                "5",
                "5",
                "5",
                "5",
            ],
            "min_infiltration_capacity": [
                "0",
                "0",
                "0",
                "0.5",
                "0.5",
                "0.5",
                "0",
                "0",
                "0",
                "1",
                "1",
                "1",
                "1",
                "1",
                "1",
            ],
            "infiltration_decay_constant": [
                "0",
                "0",
                "0",
                "3",
                "3",
                "3",
                "0",
                "0",
                "0",
                "3",
                "3",
                "3",
                "3",
                "3",
                "3",
            ],
            "infiltration_recovery_constant": [
                "0",
                "0",
                "0",
                "0.1",
                "0.1",
                "0.1",
                "0",
                "0",
                "0",
                "0.1",
                "0.1",
                "0.1",
                "0.1",
                "0.1",
                "0.1",
            ],
        }

    @property
    def materials_defaults(self):
        return {
            "id": ["0", "1", "2", "3", "4", "5", "6", "7", "8"],
            "description": [
                "Concrete",
                "PVC",
                "Gres",
                "Cast iron",
                "Brickwork",
                "HPE",
                "HDPE",
                "Plate iron",
                "Steel",
            ],
            "friction_type": ["2", "2", "2", "2", "2", "2", "2", "2", "2"],
            "friction_coefficient": [
                "0.0145",
                "0.011",
                "0.0115",
                "0.0135",
                "0.016",
                "0.011",
                "0.011",
                "0.0135",
                "0.013",
            ],
        }

    @property
    def settings_tables_defaults(self):
        """Settings tables defaults map."""
        tables_defaults = {
            "model_settings": self.model_settings_defaults,
            "numerical_settings": self.numerical_settings_defaults,
            "simulation_template_settings": self.simulation_template_settings_defaults,
            "time_step_settings": self.time_step_settings_defaults,
            "physical_settings": self.physical_settings_defaults,
            "initial_conditions": self.initial_conditions_defaults,
            "interception": self.interception_defaults,
            "dry_weather_flow_distribution": self.dry_weather_flow_distribution_defaults,
            "material": self.materials_defaults,
            "surface_parameters": self.surface_parameters_defaults,
        }
        return tables_defaults

    @property
    def user_input_settings(self):
        """Get user input settings."""
        user_settings = scan_widgets_parameters(
            self,
            get_combobox_text=True,
            remove_postfix=False,
            lineedits_as_float_or_none=False,
        )
        crs = user_settings["crs"]
        epsg = crs.authid()
        user_settings["epsg_code"] = int(epsg.split(":")[-1]) if epsg else 0
        use_1d_checked = self.use_1d_flow_group.isChecked()
        use_2d_checked = self.use_2d_flow_group.isChecked()
        user_settings["use_advection_1d"] = 3 if use_1d_checked else 0
        user_settings["use_advection_2d"] = 1 if use_2d_checked else 0
        if use_2d_checked:
            dem_file = os.path.basename(user_settings["dem_file"])
            user_settings["dem_file"] = dem_file if dem_file else None
            sloping_checked = user_settings[
                "friction_shallow_water_depth_correction_sloping"
            ]
            user_settings["friction_shallow_water_depth_correction"] = (
                3 if sloping_checked else 0
            )
            user_settings["limiter_waterlevel_gradient_2d"] = (
                0 if sloping_checked else 1
            )
            user_settings["limiter_slope_crossectional_area_2d"] = (
                3 if sloping_checked else 0
            )
            user_settings["limiter_slope_friction_2d"] = 1 if sloping_checked else 0
            user_settings["limiter_slope_thin_water_layer"] = (
                0.1 if sloping_checked else None
            )
        friction_type_text = user_settings["friction_type_text"]
        user_settings["friction_type"] = int(friction_type_text.split(":")[0])
        friction_coefficient_file = os.path.basename(
            user_settings["friction_coefficient_file"]
        )
        user_settings["friction_coefficient_file"] = (
            friction_coefficient_file if friction_coefficient_file else None
        )
        if not use_1d_checked or use_2d_checked:
            user_settings["manhole_aboveground_storage_area"] = None
        time_step = user_settings["time_step"]
        output_time_step_text = user_settings["output_time_step_text"]
        output_time_step_map = {
            "0-3 hours": 300,
            "3-12 hours": 900,
            "12-24 hours": 1800,
            "> 24 hours": 3600,
        }
        suggested_ots = output_time_step_map[output_time_step_text]
        out_timestep_mod = suggested_ots % time_step
        output_time_step = (
            suggested_ots + (time_step - out_timestep_mod)
            if out_timestep_mod
            else suggested_ots
        )
        user_settings["output_time_step"] = output_time_step
        user_settings["use_0d_inflow"] = self.use_0d_inflow_checkbox.isChecked()
        user_settings["use_1d_flow"] = 1 if use_1d_checked else 0
        user_settings["use_2d_flow"] = 1 if use_2d_checked else 0
        user_settings["use_2d_rain"] = 1 if use_2d_checked else 0
        user_settings["use_nested_newton"] = 1 if use_1d_checked else 0
        if use_1d_checked and not use_2d_checked:
            max_degree = 700
        elif use_1d_checked and use_2d_checked:
            max_degree = 7
        else:
            max_degree = 5
        user_settings["max_degree_gauss_seidel"] = max_degree

        return user_settings

    def raster_filepaths(self):
        """Get raster filepaths."""
        dem_file = self.dem_file.filePath()
        friction_coefficient_file = self.friction_coefficient_file.filePath()
        return dem_file, friction_coefficient_file

    def collect_new_schematisation_settings(self):
        """Get all needed settings."""
        all_schematisation_settings = defaultdict(dict)
        user_settings = self.user_input_settings
        # force defaults for these tables
        force_default = [
            "material",
            "dry_weather_flow_distribution",
            "surface_parameters",
        ]
        for table_name, settings in self.settings_tables_defaults.items():
            for entry, default_value in settings.items():
                if entry in user_settings and table_name not in force_default:
                    all_schematisation_settings[table_name][entry] = user_settings[
                        entry
                    ]
                else:
                    all_schematisation_settings[table_name][entry] = default_value
        return all_schematisation_settings
