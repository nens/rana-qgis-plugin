# 3Di Models and Simulations for QGIS, licensed under GPLv2 or (at your option) any later version
# Copyright (C) 2023 by Lutra Consulting for 3Di Water Management
import hashlib
import json
import os
import tempfile
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from operator import attrgetter
from time import sleep
from typing import List
from zipfile import ZIP_DEFLATED, ZipFile

import requests
from qgis.core import QgsVectorLayer
from qgis.PyQt.QtCore import QSettings, Qt
from qgis.PyQt.QtGui import (
    QBrush,
    QColor,
    QStandardItem,
    QStandardItemModel,
)
from qgis.utils import plugins
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalSchematisation, list_local_schematisations

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls


class LogLevels(Enum):
    """Model Checker log levels."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    FUTURE_ERROR = "FUTURE_ERROR"


class TreeViewLogger(object):
    """Utility class for logging in TreeView"""

    def __init__(self, tree_view=None, header=None):
        self.tree_view = tree_view
        self.header = header
        self.model = QStandardItemModel()
        self.tree_view.setModel(self.model)
        self.levels_colors = {
            LogLevels.INFO.value: QColor(Qt.black),
            LogLevels.WARNING.value: QColor(229, 144, 80),
            LogLevels.ERROR.value: QColor(Qt.red),
            LogLevels.FUTURE_ERROR.value: QColor(102, 51, 153),
        }
        self.initialize_view()

    def clear(self):
        """Clear list view model."""
        self.tree_view.model().clear()

    def initialize_view(self):
        """Clear list view model and set header columns if available."""
        self.tree_view.model().clear()
        if self.header:
            self.tree_view.model().setHorizontalHeaderLabels(self.header)

    def log_result_row(self, row, log_level):
        """Show row data with proper log level styling."""
        text_color = self.levels_colors[log_level]
        if self.tree_view is not None:
            items = []
            for value in row:
                item = QStandardItem(str(value))
                item.setForeground(QBrush(text_color))
                items.append(item)
            self.model.appendRow(items)
            for i in range(len(self.header)):
                self.tree_view.resizeColumnToContents(i)
        else:
            print(row)


TEMPDIR = tempfile.gettempdir()
PLUGIN_PATH = os.path.dirname(os.path.realpath(__file__))
CACHE_PATH = os.path.join(PLUGIN_PATH, "_cached_data")
TEMPLATE_PATH = os.path.join(CACHE_PATH, "templates.json")
INITIAL_WATERLEVELS_TEMPLATE = os.path.join(CACHE_PATH, "initial_waterlevels.json")
INITIAL_CONCENTRATIONS_TEMPLATE = os.path.join(
    CACHE_PATH, "initial_concentrations.json"
)
BOUNDARY_CONDITIONS_TEMPLATE = os.path.join(CACHE_PATH, "boundary_conditions.json")
LATERALS_FILE_TEMPLATE = os.path.join(CACHE_PATH, "laterals.json")
DWF_FILE_TEMPLATE = os.path.join(CACHE_PATH, "dwf.json")
CHUNK_SIZE = 1024**2
RADAR_ID = "d6c2347d-7bd1-4d9d-a1f6-b342c865516f"
API_DATETIME_FORMAT = "%Y-%m-%dT%H:%M:%S.%f%z"
USER_DATETIME_FORMAT = "%Y-%m-%d %H:%M:%S"


class RainEventTypes(Enum):
    CONSTANT = "Constant"
    FROM_CSV = "From CSV"
    FROM_NETCDF = "From NetCDF"
    DESIGN = "Design"
    RADAR = "Radar - NL Only"


class WindEventTypes(Enum):
    CONSTANT = "Constant"
    CUSTOM = "Custom"


class UploadFileStatus(Enum):
    """Possible actions on files upload."""

    NO_CHANGES_DETECTED = "NO CHANGES DETECTED"
    CHANGES_DETECTED = "CHANGES DETECTED"
    NEW = "NEW"
    DELETED_LOCALLY = "DELETED LOCALLY"
    INVALID_REFERENCE = "INVALID REFERENCE!"


class UploadFileType(Enum):
    """File types of the uploaded files."""

    DB = "DB"
    RASTER = "RASTER"


class FileState(Enum):
    """Possible uploaded file states."""

    CREATED = "created"
    UPLOADED = "uploaded"
    PROCESSED = "processed"
    ERROR = "error"
    REMOVED = "removed"


class ThreediFileState(Enum):
    """Possible 3Di file states."""

    PROCESSING = "processing"
    VALID = "valid"
    INVALID = "invalid"


class ThreediModelTaskStatus(Enum):
    """Possible 3Di Model Task statuses."""

    PENDING = "pending"
    SENT = "sent"
    RECEIVED = "received"
    STARTED = "started"
    SUCCESS = "success"
    FAILURE = "failure"
    REVOKED = "revoked"


class BreachSourceType(Enum):
    POTENTIAL_BREACHES = "Potential breaches"
    FLOWLINES = "1D2D Flowlines"


numerical_diffusion_limiter_to_int = {"Off": 0, "Standard": 1}
int_to_numerical_diffusion_limiter = {
    v: k for (k, v) in numerical_diffusion_limiter_to_int.items()
}


def mmh_to_ms(mmh_value):
    """Converting values from 'mm/h' to the 'm/s'."""
    ms_value = mmh_value / 3600 * 0.001
    return ms_value


def ms_to_mmh(ms_value):
    """Converting values from 'm/s' to the 'mm/h'."""
    mmh_value = ms_value * 3600 * 1000
    return mmh_value


def mmtimestep_to_mmh(value, timestep, units="s"):
    """Converting values from 'mm/timestep' to the 'mm/h'."""
    if units == "s":
        timestep_seconds = timestep
    elif units == "mins":
        timestep_seconds = timestep * 60
    elif units == "hrs":
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / timestep_seconds
    mmh_value = value_per_second * 3600
    return mmh_value


def mmh_to_mmtimestep(value, timestep, units="s"):
    """Converting values from 'mm/h' to the 'mm/timestep'."""
    if units == "s":
        timestep_seconds = timestep
    elif units == "mins":
        timestep_seconds = timestep * 60
    elif units == "hrs":
        timestep_seconds = timestep * 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    value_per_second = value / 3600
    mmtimestep_value = value_per_second * timestep_seconds
    return mmtimestep_value


def units_to_seconds(units="s"):
    """Converting timestep to seconds."""
    if units == "s":
        seconds_per_unit = 1
    elif units == "mins":
        seconds_per_unit = 60
    elif units == "hrs":
        seconds_per_unit = 3600
    else:
        raise ValueError(f"Unsupported timestep units format ({units})!")
    return seconds_per_unit


def convert_timeseries_to_seconds(timeseries, units="s"):
    """Converting timeseries to seconds."""
    seconds_per_unit = units_to_seconds(units)
    converted_timeseries = [[t * seconds_per_unit, v] for (t, v) in timeseries]
    return converted_timeseries


def load_saved_templates():
    """Loading parameters from saved template."""
    items = OrderedDict()
    with open(TEMPLATE_PATH, "a"):
        os.utime(TEMPLATE_PATH, None)
    with open(TEMPLATE_PATH, "r+") as json_file:
        data = {}
        if os.path.getsize(TEMPLATE_PATH):
            data = json.load(json_file)
        for name, parameters in sorted(data.items()):
            items[name] = parameters
    return items


def read_json_data(json_filepath):
    """Parse and return data from JSON file."""
    with open(json_filepath, "r+") as json_file:
        data = json.load(json_file)
        return data


def write_json_data(values, json_file_template):
    """Writing data to the JSON file."""
    with open(json_file_template, "w") as json_file:
        jsonf = json.dumps(values)
        json_file.write(jsonf)


def write_template(template_name, simulation_template):
    """Writing parameters as a template."""
    with open(TEMPLATE_PATH, "a"):
        os.utime(TEMPLATE_PATH, None)
    with open(TEMPLATE_PATH, "r+") as json_file:
        data = {}
        if os.path.getsize(TEMPLATE_PATH):
            data = json.load(json_file)
        data[template_name] = simulation_template
        jsonf = json.dumps(data)
        json_file.seek(0)
        json_file.write(jsonf)
        json_file.truncate()


def upload_local_file(upload, filepath):
    """Upload file."""
    with open(filepath, "rb") as file:
        response = requests.put(upload.put_url, data=file)
        return response


def file_cached(file_path):
    """Checking if file exists."""
    return os.path.isfile(file_path)


def get_download_file(download, file_path):
    """Getting file from Download object and writing it under given path."""
    r = requests.get(download.get_url, stream=True, timeout=15)
    with open(file_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
            if chunk:
                f.write(chunk)


def is_file_checksum_equal(file_path, etag):
    """Checking if etag (MD5 checksum) matches checksum calculated for a given file."""
    with open(file_path, "rb") as file_to_check:
        data = file_to_check.read()
        md5_returned = hashlib.md5(data).hexdigest()
        return etag == md5_returned


def zip_into_archive(file_path, compression=ZIP_DEFLATED):
    """Zip file."""
    zip_filename = os.path.basename(file_path)
    zip_filepath = file_path.rsplit(".", 1)[0] + ".zip"
    with ZipFile(zip_filepath, "w", compression=compression) as zf:
        zf.write(file_path, arcname=zip_filename)
    return zip_filepath


def unzip_archive(zip_filepath, location=None):
    """Unzip archive content."""
    if not location:
        location = os.path.dirname(zip_filepath)
    with ZipFile(zip_filepath, "r") as zf:
        content_list = zf.namelist()
        zf.extractall(location)
        return content_list


def extract_error_message(e):
    """Extracting useful information from ApiException exceptions."""
    error_body = e.body
    try:
        if isinstance(error_body, str):
            error_body = json.loads(error_body)
        if "detail" in error_body:
            error_details = error_body["detail"]
        elif "details" in error_body:
            error_details = error_body["details"]
        elif "errors" in error_body:
            errors = error_body["errors"]
            try:
                error_parts = [
                    f"{err['reason']} ({err['instance']['related_object']})"
                    for err in errors
                ]
            except TypeError:
                error_parts = list(errors.values())
            error_details = "\n" + "\n".join(error_parts)
        else:
            error_details = str(error_body)
    except json.JSONDecodeError:
        error_details = str(error_body)
    error_msg = f"Error: {error_details}"
    return error_msg


def handle_csv_header(header: List[str]):
    """
    Handle CSV header.
    Return None if fetch successful or error message if file is empty or have invalid structure.
    """
    error_message = None
    if not header:
        error_message = "CSV file is empty!"
        return error_message
    if "id" not in header:
        error_message = "Missing 'id' column in CSV file!"
    if "timeseries" not in header:
        error_message = "Missing 'timeseries' column in CSV file!"
    return error_message


def apply_24h_timeseries(start_datetime, end_datetime, timeseries):
    """Applying 24 hours Dry Weather Flow timeseries based on simulation duration."""
    start_day = datetime(start_datetime.year, start_datetime.month, start_datetime.day)
    end_day = datetime(end_datetime.year, end_datetime.month, end_datetime.day)
    hour_in_sec = 3600
    day_in_sec = hour_in_sec * 24
    full_days_delta = end_day - start_day
    full_days_duration = full_days_delta.days + 1
    full_days_sec = full_days_duration * day_in_sec
    flow_ts = [ts[-1] for ts in timeseries]
    extended_flow_ts = flow_ts + flow_ts[1:] * (
        full_days_duration - 1
    )  # skipping 0.0 time step while extending TS
    full_days_seconds_range = range(0, full_days_sec + hour_in_sec, hour_in_sec)
    start_time_delta = start_datetime - start_day
    end_time_delta = end_datetime - start_day
    start_timestep = (start_time_delta.total_seconds() // hour_in_sec) * hour_in_sec
    end_timestep = (end_time_delta.total_seconds() // hour_in_sec) * hour_in_sec
    timestep = 0.0
    new_timeseries = []
    for extended_timestep, flow in zip(full_days_seconds_range, extended_flow_ts):
        if extended_timestep < start_timestep:
            continue
        elif end_timestep >= extended_timestep >= start_timestep:
            new_timeseries.append((timestep, flow))
            timestep += hour_in_sec
        else:
            break
    return new_timeseries


def split_to_even_chunks(collection, chunk_length):
    """Split collection to even chunks list."""
    return [
        collection[i : i + chunk_length]
        for i in range(0, len(collection), chunk_length)
    ]


def intervals_are_even(time_series):
    """Check if intervals in the time series are all even."""
    expected_interval = time_series[1][0] - time_series[0][0]
    time_steps = [time_step for time_step, value in time_series]
    for start_time_step, end_time_step in zip(time_steps, time_steps[1:]):
        if end_time_step - start_time_step != expected_interval:
            return False
    return True


def parse_version_number(version_str):
    """Parse version number in a string format and convert it into list of an integers."""
    version = [int(i) for i in version_str.split(".") if i.isnumeric()]
    return version


def constains_only_ascii(text):
    return all(ord(c) < 128 for c in text)


def parse_timeseries(timeseries: str):
    """Parse the timeseries from the given string."""
    return [[float(f) for f in line.split(",")] for line in timeseries.split("\n")]


def translate_illegal_chars(
    text, illegal_characters=r'\/:*?"<>|', replacement_character="-"
):
    """Remove illegal characters from the text."""
    sanitized_text = "".join(
        char if char not in illegal_characters else replacement_character
        for char in text
    )
    return sanitized_text


def geopackage_layer(gpkg_path, table_name, layer_name=None):
    """Creating vector layer out of GeoPackage source."""
    uri = f"{gpkg_path}|layername={table_name}"
    layer_name = table_name if layer_name is None else layer_name
    vlayer = QgsVectorLayer(uri, layer_name, "ogr")
    return vlayer


def extract_error_message(e):
    """Extracting useful information from ApiException exceptions."""
    error_body = e.body
    try:
        if isinstance(error_body, str):
            error_body = json.loads(error_body)
        if "detail" in error_body:
            error_details = error_body["detail"]
        elif "details" in error_body:
            error_details = error_body["details"]
        elif "errors" in error_body:
            errors = error_body["errors"]
            try:
                error_parts = [
                    f"{err['reason']} ({err['instance']['related_object']})"
                    for err in errors
                ]
            except TypeError:
                error_parts = list(errors.values())
            error_details = "\n" + "\n".join(error_parts)
        else:
            error_details = str(error_body)
    except json.JSONDecodeError:
        error_details = str(error_body)
    return f"Error: {error_details}"


class NestedObject:
    """A class to convert a nested dictionary into an object."""

    def __init__(self, data):
        for key, value in data.items():
            if isinstance(value, (list, tuple)):
                setattr(
                    self,
                    key,
                    [NestedObject(x) if isinstance(x, dict) else x for x in value],
                )
            else:
                setattr(
                    self, key, NestedObject(value) if isinstance(value, dict) else value
                )


class SchematisationRasterReferences:
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
            for k, v in SchematisationRasterReferences.settings_to_api_raster_types().items()
        }
        return raster_type_map

    @staticmethod
    def api_client_raster_type(settings_raster_type):
        try:
            return SchematisationRasterReferences.settings_to_api_raster_types()[
                settings_raster_type
            ]
        except KeyError:
            return settings_raster_type

    @staticmethod
    def settings_raster_type(api_raster_type):
        try:
            return SchematisationRasterReferences.api_to_settings_raster_types()[
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


class BuildOptionActions(Enum):
    CREATED = "created"
    LOADED = "loaded"
    DOWNLOADED = "downloaded"


def load_remote_schematisation(
    communications,
    schematisation,
    revision,
    progress_bar,
    working_dir,
    threedi_api,
):
    """Download and load a schematisation from the server."""
    if isinstance(schematisation, dict):
        schematisation = NestedObject(schematisation)
    if isinstance(revision, dict):
        revision = NestedObject(revision)

    required_files = download_required_files(
        communications,
        schematisation,
        revision,
        False,
        progress_bar,
        working_dir,
        threedi_api,
    )

    if required_files is not None:
        (
            downloaded_local_schematisation,
            custom_geopackage_filepath,
            wip_replace_requested,
        ) = required_files
        if not downloaded_local_schematisation:
            communications.log_warn("Unable to load local schematisation")
            return

        assert revision.number in downloaded_local_schematisation.revisions
        load_local_schematisation(
            communications,
            local_schematisation=downloaded_local_schematisation.wip_revision
            if wip_replace_requested
            else downloaded_local_schematisation.revisions[revision.number],
            action=BuildOptionActions.DOWNLOADED,
            custom_geopackage_filepath=custom_geopackage_filepath,
        )
        wip_revision = downloaded_local_schematisation.wip_revision
        if wip_revision is not None:
            settings = QSettings("3di", "qgisplugin")
            settings.setValue(
                "last_used_geopackage_path", wip_revision.schematisation_dir
            )


def download_required_files(
    communications,
    schematisation,
    revision,
    is_latest_revision,
    external_progress_bar,
    working_dir,
    threedi_api,
):
    """Download required schematisation revision files."""
    try:
        progress_bar = external_progress_bar
        schematisation_pk = schematisation.id
        schematisation_name = schematisation.name

        # Move code from M&S plugin's SchematisationDownload to make this function more or less standalone.
        tc = ThreediCalls(threedi_api)
        revisions = tc.fetch_schematisation_revisions(schematisation_pk)
        local_schematisations = list_local_schematisations(
            working_dir, use_config_for_revisions=False
        )
        downloaded_geopackage_filepath = None
        downloaded_local_schematisation = None
        wip_replace_requested = False

        revision_pk = revision.id
        revision_number = revision.number
        revision_sqlite = revision.sqlite
        if not is_latest_revision:
            latest_online_revision = (
                max([rev.number for rev in revisions]) if revisions else None
            )
            is_latest_revision = revision_number == latest_online_revision
        try:
            local_schematisation = local_schematisations[schematisation_pk]
            local_schematisation_present = True
        except KeyError:
            local_schematisation = LocalSchematisation(
                working_dir, schematisation_pk, schematisation_name, create=True
            )
            local_schematisations[schematisation_pk] = local_schematisation
            local_schematisation_present = False

        def decision_tree():
            replace, store, cancel = "Replace", "Store", "Cancel"
            title = "Pick action"
            question = f"Replace local WIP or store as a revision {revision_number}?"
            wip_replace_requested = False
            picked_action_name = communications.custom_ask(
                None, title, question, replace, store, cancel
            )
            if picked_action_name == replace:
                # Replace
                local_schematisation.set_wip_revision(revision_number)
                schema_db_dir = local_schematisation.wip_revision.schematisation_dir
                wip_replace_requested = True
            elif picked_action_name == store:
                # Store as a separate revision
                if revision_number in local_schematisation.revisions:
                    question = f"Replace local revision {revision_number} or Cancel?"
                    picked_action_name = communications.custom_ask(
                        None, title, question, "Replace", "Cancel"
                    )
                    if picked_action_name == "Replace":
                        local_revision = local_schematisation.add_revision(
                            revision_number
                        )
                        schema_db_dir = local_revision.schematisation_dir
                    else:
                        schema_db_dir = None
                else:
                    local_revision = local_schematisation.add_revision(revision_number)
                    schema_db_dir = local_revision.schematisation_dir
            else:
                schema_db_dir = None
            return schema_db_dir, wip_replace_requested

        if local_schematisation_present:
            if is_latest_revision:
                if local_schematisation.wip_revision is None:
                    # WIP not exist
                    local_schematisation.set_wip_revision(revision_number)
                    schematisation_db_dir = (
                        local_schematisation.wip_revision.schematisation_dir
                    )
                else:
                    # WIP exist
                    schematisation_db_dir, wip_replace_requested = decision_tree()
            else:
                schematisation_db_dir, wip_replace_requested = decision_tree()
        else:
            local_schematisation.set_wip_revision(revision_number)
            schematisation_db_dir = local_schematisation.wip_revision.schematisation_dir
            wip_replace_requested = True

        if not schematisation_db_dir:
            return

        sqlite_download = tc.download_schematisation_revision_sqlite(
            schematisation_pk, revision_pk
        )
        revision_models = tc.fetch_schematisation_revision_3di_models(
            schematisation_pk, revision_pk
        )
        rasters_downloads = []
        for raster_file in revision.rasters or []:
            raster_download = tc.download_schematisation_revision_raster(
                raster_file.id, schematisation_pk, revision_pk
            )
            rasters_downloads.append((raster_file.name, raster_download))
        number_of_steps = len(rasters_downloads) + 1

        gridadmin_file, gridadmin_download = (None, None)
        gridadmin_file_gpkg, gridadmin_download_gpkg = (None, None)
        ignore_gridadmin_error_messages = [
            "Gridadmin file not found",
            "Geopackage file not found",
        ]
        for revision_model in sorted(
            revision_models, key=attrgetter("id"), reverse=True
        ):
            try:
                gridadmin_file, gridadmin_download = (
                    tc.fetch_3di_model_gridadmin_download(revision_model.id)
                )
                if gridadmin_download is not None:
                    gridadmin_file_gpkg, gridadmin_download_gpkg = (
                        tc.fetch_3di_model_geopackage_download(revision_model.id)
                    )
                    number_of_steps += 1
                    break
            except ApiException as e:
                error_msg = extract_error_message(e)
                if not any(
                    ignore_error_msg in error_msg
                    for ignore_error_msg in ignore_gridadmin_error_messages
                ):
                    raise
        if revision_number not in local_schematisation.revisions:
            local_schematisation.add_revision(revision_number)
        zip_filepath = os.path.join(
            schematisation_db_dir, revision_sqlite.file.filename
        )
        progress_bar.setMaximum(number_of_steps)
        current_progress = 0
        progress_bar.setValue(current_progress)
        get_download_file(sqlite_download, zip_filepath)
        content_list = unzip_archive(zip_filepath)
        os.remove(zip_filepath)
        schematisation_db_file = content_list[0]
        current_progress += 1
        progress_bar.setValue(current_progress)
        if gridadmin_download is not None:
            grid_filepath = os.path.join(
                local_schematisation.revisions[revision_number].grid_dir,
                gridadmin_file.filename,
            )
            get_download_file(gridadmin_download, grid_filepath)
            current_progress += 1
            progress_bar.setValue(current_progress)
        if gridadmin_download_gpkg is not None:
            gpkg_filepath = os.path.join(
                local_schematisation.revisions[revision_number].grid_dir,
                gridadmin_file_gpkg.filename,
            )
            get_download_file(gridadmin_download_gpkg, gpkg_filepath)
            current_progress += 1
            progress_bar.setValue(current_progress)
        for raster_filename, raster_download in rasters_downloads:
            raster_filepath = os.path.join(
                schematisation_db_dir, "rasters", raster_filename
            )
            get_download_file(raster_download, raster_filepath)
            current_progress += 1
            progress_bar.setValue(current_progress)
        downloaded_local_schematisation = local_schematisation
        expected_geopackage_path = os.path.join(
            schematisation_db_dir, schematisation_db_file
        )
        if expected_geopackage_path.lower().endswith(".sqlite"):
            expected_geopackage_path = (
                expected_geopackage_path.rsplit(".", 1)[0] + ".gpkg"
            )
        if os.path.isfile(expected_geopackage_path):
            downloaded_geopackage_filepath = expected_geopackage_path
        sleep(1)
        settings = QSettings()
        settings.setValue("threedi/last_schematisation_folder", schematisation_db_dir)
        msg = f"Schematisation '{schematisation_name} (revision {revision_number})' downloaded!"
        communications.bar_info(msg)

        return (
            downloaded_local_schematisation,
            downloaded_geopackage_filepath,
            wip_replace_requested,
        )
    except ApiException as e:
        error_msg = extract_error_message(e)
        communications.show_error(error_msg)
    except Exception as e:
        error_msg = f"Error: {e}"
        communications.show_error(error_msg)

    return None, None, None


def get_plugin_instance(plugin_name):
    """Return given plugin name instance."""
    try:
        plugin_instance = plugins[plugin_name]
    except (AttributeError, KeyError):
        plugin_instance = None
    return plugin_instance


def load_local_schematisation(
    communication,
    local_schematisation=None,
    action=BuildOptionActions.LOADED,
    custom_geopackage_filepath=None,
):
    if local_schematisation and (
        custom_geopackage_filepath or local_schematisation.schematisation_db_filepath
    ):
        try:
            geopackage_filepath = (
                local_schematisation.schematisation_db_filepath
                if not custom_geopackage_filepath
                else custom_geopackage_filepath
            )
            msg = f"Schematisation '{local_schematisation.local_schematisation.name} ({local_schematisation.number})' {action.value}!\n"
            communication.bar_info(msg)
            # Load new schematisation
            schematisation_editor = get_plugin_instance("threedi_schematisation_editor")
            communication.log_info(f"Loading {geopackage_filepath}")
            if schematisation_editor:
                schematisation_editor.load_schematisation(geopackage_filepath)
            else:
                msg += (
                    "Please use the Rana Schematisation Editor to load it to your project from the GeoPackage:"
                    f"\n{geopackage_filepath}"
                )
                communication.show_warn(msg)
        except (TypeError, ValueError):
            error_msg = "Invalid schematisation directory structure. Loading schematisation canceled."
            communication.show_error(error_msg)
