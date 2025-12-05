from collections import OrderedDict
from enum import Enum


class UploadFileType(Enum):
    """File types of the uploaded files."""

    DB = "DB"
    RASTER = "RASTER"


class UploadFileStatus(Enum):
    """Possible actions on files upload."""

    NO_CHANGES_DETECTED = "NO CHANGES DETECTED"
    CHANGES_DETECTED = "CHANGES DETECTED"
    NEW = "NEW"
    DELETED_LOCALLY = "DELETED LOCALLY"
    INVALID_REFERENCE = "INVALID REFERENCE!"



class SchematisationApiMapper:
    """This class maps types between the geopackage and the API"""

    @staticmethod
    def settings_to_api_raster_types():
        raster_type_map = {
            "friction_coefficient_file": "frict_coef_file",
            "max_infiltration_volume_file": "max_infiltration_capacity_file",
            "groundwater_hydraulic_conductivity_file": "groundwater_hydro_connectivity_file",
            "initial_water_level_file": "initial_waterlevel_file",
        }
        return raster_type_map

    @staticmethod
    def api_to_settings_raster_types():
        raster_type_map = {
            v: k
            for k, v in SchematisationApiMapper.settings_to_api_raster_types().items()
        }
        return raster_type_map

    @staticmethod
    def api_client_raster_type(settings_raster_type):
        try:
            return SchematisationApiMapper.settings_to_api_raster_types()[
                settings_raster_type
            ]
        except KeyError:
            return settings_raster_type

    @staticmethod
    def settings_raster_type(api_raster_type):
        try:
            return SchematisationApiMapper.api_to_settings_raster_types()[
                api_raster_type
            ]
        except KeyError:
            return api_raster_type

    @staticmethod
    def model_settings_rasters():
        """Rasters mapping from the Model settings layer."""
        raster_info = OrderedDict(
            (
                ("dem_file", "Digital elevation model [m MSL]"),
                ("friction_coefficient_file", "Friction coefficient [-]"),
            )
        )
        return raster_info

    @staticmethod
    def initial_conditions_rasters():
        """Rasters mapping for the Initial conditions."""
        raster_info = OrderedDict(
            (
                ("initial_groundwater_level_file", "Initial groundwater level [m MSL]"),
                ("initial_water_level_file", "Initial water level [m MSL]"),
            )
        )
        return raster_info

    @staticmethod
    def interception_rasters():
        """Rasters mapping for the Interception."""
        raster_info = OrderedDict((("interception_file", "Interception [m]"),))
        return raster_info

    @staticmethod
    def simple_infiltration_rasters():
        """Rasters mapping for the Infiltration."""
        raster_info = OrderedDict(
            (
                ("infiltration_rate_file", "Infiltration rate [mm/d]"),
                ("max_infiltration_volume_file", "Max infiltration volume [m]"),
            )
        )
        return raster_info

    @staticmethod
    def groundwater_rasters():
        """Rasters mapping for the Groundwater."""
        raster_info = OrderedDict(
            (
                (
                    "equilibrium_infiltration_rate_file",
                    "Equilibrium infiltration rate [mm/d]",
                ),
                (
                    "groundwater_hydraulic_conductivity_file",
                    "Hydraulic conductivity [m/day]",
                ),
                (
                    "groundwater_impervious_layer_level_file",
                    "Impervious layer level [m MSL]",
                ),
                ("infiltration_decay_period_file", "Infiltration decay period [d]"),
                ("initial_infiltration_rate_file", "Initial infiltration rate [mm/d]"),
                ("leakage_file", "Leakage [mm/d]"),
                ("phreatic_storage_capacity_file", "Phreatic storage capacity [-]"),
            )
        )
        return raster_info

    @staticmethod
    def interflow_rasters():
        """Rasters mapping for the Interflow."""
        raster_info = OrderedDict(
            (
                ("hydraulic_conductivity_file", "Hydraulic conductivity [m/d]"),
                ("porosity_file", "Porosity [-]"),
            )
        )
        return raster_info

    @staticmethod
    def vegetation_drag_rasters():
        """Rasters mapping for the Vegetation drag settings."""
        raster_info = OrderedDict(
            (
                ("vegetation_height_file", "Vegetation height [m]"),
                ("vegetation_stem_count_file", "Vegetation stem count [-]"),
                ("vegetation_stem_diameter_file", "Vegetation stem diameter [m]"),
                ("vegetation_drag_coefficient_file", "Vegetation drag coefficient [-]"),
            )
        )
        return raster_info

    @classmethod
    def raster_reference_tables(cls):
        """GeoPackage tables mapping with references to the rasters."""
        reference_tables = OrderedDict(
            (
                ("model_settings", cls.model_settings_rasters()),
                ("initial_conditions", cls.initial_conditions_rasters()),
                ("interception", cls.interception_rasters()),
                ("simple_infiltration", cls.simple_infiltration_rasters()),
                ("groundwater", cls.groundwater_rasters()),
                ("interflow", cls.interflow_rasters()),
                ("vegetation_drag_2d", cls.vegetation_drag_rasters()),
            )
        )
        return reference_tables

    @classmethod
    def raster_table_mapping(cls):
        """Rasters to geopackage tables mapping."""
        table_mapping = {}
        for (
            table_name,
            raster_files_references,
        ) in cls.raster_reference_tables().items():
            for raster_type in raster_files_references.keys():
                table_mapping[raster_type] = table_name
        return table_mapping
