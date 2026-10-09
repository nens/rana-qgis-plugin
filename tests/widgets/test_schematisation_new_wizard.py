import sqlite3
from unittest.mock import MagicMock, patch

from rana_qgis_plugin.widgets.schematisation_new_wizard import (
    NewSchematisationWizard,
    UploadExistingSchematisationWizard,
)


def test_get_paths_from_geopackage_extracts_referenced_raster_fields(tmp_path):
    layer = MagicMock()
    layer.isValid.return_value = True
    layer.getFeatures.return_value = iter(
        [{"dem_file": "dem.tif", "friction_coefficient_file": None}]
    )

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationApiMapper.raster_reference_tables",
            return_value={
                "model_settings": {
                    "dem_file": "DEM",
                    "friction_coefficient_file": "Friction",
                }
            },
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.geopackage_layer",
            return_value=layer,
        ),
    ):
        paths = UploadExistingSchematisationWizard.get_paths_from_geopackage(
            tmp_path / "input.gpkg"
        )

    assert paths["model_settings"] == {
        "dem_file": "dem.tif",
        "friction_coefficient_file": None,
    }


def test_prepare_validates_sqlite_and_uses_adjacent_geopackage(tmp_path):
    sqlite_path = tmp_path / "input.sqlite"
    sqlite_path.touch()
    gpkg_path = tmp_path / "input.gpkg"
    gpkg_path.touch()
    raster_path = tmp_path / "rasters" / "dem.tif"
    raster_path.parent.mkdir()
    raster_path.touch()
    raster_paths = {"model_settings": {"dem_file": "dem.tif"}}
    communication = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.ensure_valid_schema",
            return_value=True,
        ) as validate_schema,
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.UploadExistingSchematisationWizard.get_paths_from_geopackage",
            return_value=raster_paths,
        ) as get_raster_paths,
    ):
        prepared = UploadExistingSchematisationWizard.prepare_existing_schematisation(
            sqlite_path, communication
        )

    validate_schema.assert_called_once_with(str(sqlite_path), communication)
    get_raster_paths.assert_called_once_with(str(gpkg_path))
    assert prepared == (gpkg_path, raster_paths)
    communication.show_error.assert_not_called()
    communication.show_warn.assert_not_called()


def test_prepare_stops_when_schema_is_invalid(tmp_path):
    source_path = tmp_path / "input.gpkg"
    source_path.touch()
    communication = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.ensure_valid_schema",
            return_value=False,
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.UploadExistingSchematisationWizard.get_paths_from_geopackage"
        ) as get_raster_paths,
    ):
        prepared = UploadExistingSchematisationWizard.prepare_existing_schematisation(
            source_path, communication
        )

    assert prepared is None
    get_raster_paths.assert_not_called()


def test_prepare_stops_if_sqlite_has_no_adjacent_geopackage(tmp_path):
    source_path = tmp_path / "input.sqlite"
    source_path.touch()
    communication = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.ensure_valid_schema",
            return_value=True,
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.UploadExistingSchematisationWizard.get_paths_from_geopackage"
        ) as get_raster_paths,
    ):
        prepared = UploadExistingSchematisationWizard.prepare_existing_schematisation(
            source_path, communication
        )

    assert prepared is None
    communication.show_error.assert_called_once()
    get_raster_paths.assert_not_called()


def test_prepare_blocks_missing_referenced_rasters(tmp_path):
    source_path = tmp_path / "input.gpkg"
    source_path.touch()
    communication = MagicMock()

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.ensure_valid_schema",
            return_value=True,
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.UploadExistingSchematisationWizard.get_paths_from_geopackage",
            return_value={"model_settings": {"dem_file": "missing-dem.tif"}},
        ),
    ):
        prepared = UploadExistingSchematisationWizard.prepare_existing_schematisation(
            source_path, communication
        )

    assert prepared is None
    communication.show_warn.assert_called_once()
    assert "missing-dem.tif" in communication.show_warn.call_args.args[0]


def test_upload_existing_checks_inputs_before_registering_remote_schematisation(
    qgis_application, tmp_path
):
    source_path = tmp_path / "input.gpkg"
    source_path.touch()
    organisation = MagicMock()
    communication = MagicMock()
    wizard = UploadExistingSchematisationWizard(
        object(),
        str(tmp_path),
        communication,
        {"owner": organisation},
        str(source_path),
        "project",
        "target/",
    )
    wizard.schematisation_name_page.main_widget.le_schematisation_name.setText(
        "New model"
    )

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.check_name_available",
            return_value=True,
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.UploadExistingSchematisationWizard",
            return_value=None,
        ),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard._create_schematisation_base"
        ) as create_base,
    ):
        wizard.create_schematisation()

    create_base.assert_not_called()
    assert wizard.new_schematisation is None
    assert wizard.new_local_schematisation is None


def test_copy_prepared_geopackage_and_rasters_into_local_revision(tmp_path):
    source_dir = tmp_path / "source"
    source_dir.mkdir()
    source_gpkg = source_dir / "source.gpkg"
    source_gpkg.write_bytes(b"geopackage data")
    raster_dir = source_dir / "rasters"
    raster_dir.mkdir()
    source_raster = raster_dir / "dem.tif"
    source_raster.write_bytes(b"raster data")

    local_dir = tmp_path / "local"
    local_dir.mkdir()
    local_raster_dir = tmp_path / "local_rasters"
    local_raster_dir.mkdir()
    revision = MagicMock()
    revision.schematisation_dir = str(local_dir)
    revision.raster_dir = str(local_raster_dir)

    UploadExistingSchematisationWizard.copy_existing_schematisation_content(
        source_gpkg,
        {"model_settings": {"dem_file": "dem.tif"}},
        "Local model",
        revision,
    )

    assert (local_dir / "Local model.gpkg").read_bytes() == b"geopackage data"
    assert (local_raster_dir / "dem.tif").read_bytes() == b"raster data"


def test_create_and_populate_schematisation_geopackage(tmp_path):
    geopackage = tmp_path / "generated.gpkg"
    dem = tmp_path / "dem.tif"
    dem.write_bytes(b"test raster")
    raster_dir = tmp_path / "rasters"
    raster_dir.mkdir()

    settings = {
        "model_settings": {
            "epsg_code": 28992,
            "use_1d_flow": 1,
            "use_2d_flow": 0,
        }
    }
    NewSchematisationWizard.create_and_populate_schematisation_geopackage(
        geopackage,
        settings,
        (str(dem), ""),
        raster_dir,
        MagicMock(),
    )

    assert geopackage.is_file()
    with sqlite3.connect(geopackage) as connection:
        row = connection.execute(
            "SELECT use_1d_flow, use_2d_flow FROM model_settings"
        ).fetchone()
    assert row == (1, 0)
    assert (raster_dir / "dem.tif").read_bytes() == b"test raster"
