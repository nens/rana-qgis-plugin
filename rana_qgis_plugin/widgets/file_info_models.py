"""Presentation models for the Rana file information dialog."""

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any, Optional

from rana_qgis_plugin.constant import SUPPORTED_DATA_TYPES
from rana_qgis_plugin.utils.generic import display_bytes
from rana_qgis_plugin.utils.time import format_activity_timestamp_str


@dataclass
class FieldValue:
    """A display value that records missing or invalid source data."""

    value: Any = None
    error: bool = False
    error_msg: str = ""

    @staticmethod
    def from_dict(data: Optional[dict], key: str, default: Any = None) -> "FieldValue":
        """Safely extract a value from a dictionary."""
        if data is None:
            return FieldValue(default, True, "Source unavailable")
        if key not in data:
            return FieldValue(default, True, f"Missing key: {key}")
        return FieldValue(data[key])


@dataclass
class GeneralInfo:
    """Data rendered by the distinct General box layout."""

    filename: FieldValue
    icon_name: str
    size: FieldValue
    user: FieldValue
    avatar_user: dict | None
    message: FieldValue
    last_modified: FieldValue


@dataclass
class InfoRow:
    """One label/value pair in the More Information box."""

    key: str
    value: FieldValue


@dataclass
class InfoSection:
    """A titled group of More Information rows."""

    title: str
    rows: list[InfoRow]


@dataclass
class RelatedFile:
    """One file shown in the schematisation related-files table."""

    name: FieldValue
    data_type: FieldValue
    size: FieldValue


def parse_timestamp(value: Any) -> FieldValue:
    """Parse an API timestamp while preserving an error state."""
    if not value:
        return FieldValue(value, True)
    try:
        return FieldValue(format_activity_timestamp_str(value))
    except (TypeError, ValueError, OverflowError) as error:
        return FieldValue(value, True, str(error))


class FileInfoModel:
    """Common data for the More Information box."""

    def __init__(self, descriptor: dict | None, file_data: dict | None = None):
        self.descriptor = descriptor or {}
        self.file_data = file_data or {}

    def get_related_files(self) -> list[RelatedFile]:
        return []

    def get_general_info(self) -> GeneralInfo:
        """Build the General box data without flattening its layout."""
        data_type = self.file_data.get("data_type", "")
        user = self.file_data.get("user")
        size = self.file_data.get("size")
        filename = PurePosixPath(self.file_data.get("id", "")).name
        return GeneralInfo(
            filename=FieldValue(filename, not bool(filename)),
            icon_name=data_type,
            size=FieldValue(
                display_bytes(size)
                if size is not None and data_type != "threedi_schematisation"
                else "N/A",
                size is None,
            ),
            user=self.username(user),
            avatar_user=user,
            message=FieldValue.from_dict(self.descriptor, "description", ""),
            last_modified=parse_timestamp(self.file_data.get("last_modified")),
        )

    @staticmethod
    def username(user: dict | None) -> FieldValue:
        """Build a display name from a user object."""
        if user is None:
            return FieldValue(None, True, "Source unavailable")
        given = FieldValue.from_dict(user, "given_name", "")
        family = FieldValue.from_dict(user, "family_name", "")
        name = f"{given.value} {family.value}".strip() or None
        return FieldValue(
            name, given.error or family.error, given.error_msg or family.error_msg
        )

    def get_more_section(self) -> InfoSection:
        """Build common More Information rows."""
        data_type = self.file_data.get("data_type", "")
        status = self.descriptor.get("status") or {}
        status_value = status.get("id", "")
        status_message = (status.get("message_i18n") or {}).get("msg")
        if status_message:
            status_value = f"{status_value}: {status_message}"
        size = self.file_data.get("size")
        rows = [
            InfoRow("Projection", self.get_projection()),
            InfoRow("Type", FieldValue(SUPPORTED_DATA_TYPES.get(data_type, data_type))),
            InfoRow("Status", FieldValue(status_value)),
        ]
        if data_type != "threedi_schematisation":
            rows.append(
                InfoRow(
                    "Storage",
                    FieldValue(
                        display_bytes(size) if size is not None else None, size is None
                    ),
                )
            )
        return InfoSection("More information", rows)

    def get_projection(self) -> FieldValue:
        """Return the best available projection."""
        meta = self.descriptor.get("meta") or {}
        projection = (meta.get("extent") or {}).get("crs") or (
            meta.get("grid") or {}
        ).get("crs")
        return FieldValue(projection, projection is None)


class ScenarioFileInfoModel(FileInfoModel):
    """Scenario-specific More Information data."""

    def get_more_section(self) -> InfoSection:
        meta = self.descriptor.get("meta") or {}
        simulation = meta.get("simulation") or {}
        schematisation = meta.get("schematisation") or {}
        software = simulation.get("software") or {}
        interval = simulation.get("interval") or []
        return InfoSection(
            "Scenario",
            super().get_more_section().rows
            + [
                InfoRow("Simulation name", FieldValue.from_dict(simulation, "name")),
                InfoRow("Simulation ID", FieldValue.from_dict(simulation, "id")),
                InfoRow(
                    "Schematisation name", FieldValue.from_dict(schematisation, "name")
                ),
                InfoRow(
                    "Schematisation ID", FieldValue.from_dict(schematisation, "id")
                ),
                InfoRow(
                    "Schematisation version",
                    FieldValue.from_dict(schematisation, "version"),
                ),
                InfoRow(
                    "Revision ID", FieldValue.from_dict(schematisation, "revision_id")
                ),
                InfoRow("Model ID", FieldValue.from_dict(schematisation, "model_id")),
                InfoRow("Model software", FieldValue.from_dict(software, "id")),
                InfoRow("Software version", FieldValue.from_dict(software, "version")),
                InfoRow(
                    "Start",
                    parse_timestamp(interval[0])
                    if len(interval) > 0
                    else FieldValue(None, True),
                ),
                InfoRow(
                    "End",
                    parse_timestamp(interval[1])
                    if len(interval) > 1
                    else FieldValue(None, True),
                ),
            ],
        )


class SchematisationFileInfoModel(FileInfoModel):
    """Schematisation-specific More Information data."""

    def __init__(
        self,
        descriptor: dict | None,
        file_data: dict | None = None,
        schematisation_data: dict | None = None,
        threedi_model_data: Any = None,
    ):
        super().__init__(descriptor, file_data)
        self.schematisation_data: dict | None = schematisation_data
        self.threedi_model_data: Any = threedi_model_data

    def schematisation_obj(self) -> dict:
        """Return the fetched schematisation data."""
        return self.schematisation_data or {}

    def threedi_model(self) -> Any:
        """Return the fetched latest valid ThreediModel, or None."""
        return self.threedi_model_data

    def get_more_section(self) -> InfoSection:
        """Build schematisation and revision metadata rows."""
        schematisation = self.schematisation_obj().get("schematisation", {})
        revision = self.schematisation_obj().get("latest_revision", {})
        metadata = schematisation.get("meta") or {}
        latest_revision_model = self.threedi_model()
        created_by = (
            " ".join(
                part
                for part in (
                    schematisation.get("created_by_first_name"),
                    schematisation.get("created_by_last_name"),
                )
                if part
            )
            or None
        )
        return InfoSection(
            "Schematisation",
            super().get_more_section().rows
            + [
                InfoRow(
                    "Schematisation name", FieldValue.from_dict(schematisation, "name")
                ),
                InfoRow(
                    "Schematisation ID", FieldValue.from_dict(schematisation, "id")
                ),
                InfoRow(
                    "Schematisation description",
                    FieldValue.from_dict(metadata, "description"),
                ),
                InfoRow(
                    "Schematisation created by",
                    FieldValue(created_by, created_by is None),
                ),
                InfoRow(
                    "Schematisation created on",
                    parse_timestamp(schematisation.get("created")),
                ),
                InfoRow(
                    "Schematisation tags",
                    FieldValue(value="; ".join(schematisation["tags"]))
                    if "tags" in schematisation
                    else FieldValue.from_dict(schematisation, "tags"),
                ),
                InfoRow("Latest revision ID", FieldValue.from_dict(revision, "id")),
                InfoRow(
                    "Latest revision number", FieldValue.from_dict(revision, "number")
                ),
                InfoRow(
                    "Latest revision valid", FieldValue.from_dict(revision, "is_valid")
                ),
                InfoRow(
                    "Latest revision is simulation ready",
                    FieldValue(
                        value=latest_revision_model is not None,
                        error=(not schematisation),
                    ),
                ),
                InfoRow(
                    "Node count",
                    FieldValue(
                        value=latest_revision_model.nodes_count,
                    )
                    if latest_revision_model
                    else FieldValue(error=True),
                ),
                InfoRow(
                    "Line count",
                    FieldValue(
                        value=latest_revision_model.lines_count,
                    )
                    if latest_revision_model
                    else FieldValue(error=True),
                ),
            ],
        )

    def get_projection(self) -> FieldValue:
        """Return the projection from the DEM raster when available."""
        revision = self.schematisation_obj().get("latest_revision", {})
        if revision:
            dem = next(
                (
                    raster
                    for raster in revision.get("rasters", [])
                    if raster.get("type") == "dem_file"
                ),
                None,
            )
            if dem and dem.get("epsg_code"):
                return FieldValue(f"EPSG:{dem['epsg_code']}")
        return super().get_projection()

    def get_related_files(self) -> list[RelatedFile]:
        """Build the related-files table data."""
        revision = self.schematisation_obj().get("latest_revision", {})
        rows = []
        sqlite_file = (revision.get("sqlite") or {}).get("file")
        if sqlite_file:
            rows.append(
                RelatedFile(
                    FieldValue(sqlite_file.get("filename")),
                    FieldValue(sqlite_file.get("type")),
                    FieldValue(display_bytes(sqlite_file.get("size", 0))),
                )
            )
        for raster in revision.get("rasters", []):
            file_data = raster.get("file")
            if file_data:
                rows.append(
                    RelatedFile(
                        FieldValue(file_data.get("filename")),
                        FieldValue(raster.get("type")),
                        FieldValue(file_data.get("size", 0)),
                    )
                )
        if revision.get("is_simulation_ready"):
            rows.extend(
                RelatedFile(FieldValue(name), FieldValue("gridadmin"), FieldValue(0))
                for name in ("gridadmin.h5", "gridadmin.gpkg")
            )
        return rows


def get_file_info_model_class(data_type: str) -> type[FileInfoModel]:
    """Return the model class for a given file type."""
    return {
        "scenario": ScenarioFileInfoModel,
        "threedi_schematisation": SchematisationFileInfoModel,
    }.get(data_type, FileInfoModel)
