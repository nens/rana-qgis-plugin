import sqlite3
from unittest.mock import MagicMock, patch

from qgis.PyQt.QtWidgets import QDialog

from rana_qgis_plugin.widgets.schematisation_new_wizard import (
    NewSchematisationWizard,
    SchematisationWizardBase,
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
        paths = SchematisationWizardBase.get_paths_from_geopackage(
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
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase.get_paths_from_geopackage",
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
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase.get_paths_from_geopackage"
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
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase.get_paths_from_geopackage"
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
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase.get_paths_from_geopackage",
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
        patch.object(wizard, "check_name_available", return_value=True),
        patch.object(wizard, "_create_schematisation_base") as create_base,
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


def test_from_scratch_wizard_exposes_raster_references_for_initial_upload(
    qgis_application, tmp_path
):
    communication = MagicMock()
    wizard = NewSchematisationWizard(
        object(),
        str(tmp_path),
        communication,
        {"owner": MagicMock()},
        "project",
        "target/",
    )
    wizard.schematisation_name_page = MagicMock()
    wizard.schematisation_name_page.name = "New model"
    wizard.schematisation_name_page.description = "Description"
    wizard.schematisation_name_page.owner = "owner"
    wizard.schematisation_settings_page = MagicMock()
    wizard.schematisation_settings_page.settings_are_valid = True
    wizard.schematisation_settings_page.main_widget.collect_new_schematisation_settings.return_value = {}
    wizard.schematisation_settings_page.main_widget.raster_filepaths.return_value = (
        "dem.tif",
        "",
    )
    schematisation = MagicMock(id="schema-id", name="New model")
    local_schematisation = MagicMock()
    wip_revision = MagicMock(
        schematisation_dir=str(tmp_path / "schema"),
        raster_dir=str(tmp_path / "rasters"),
    )
    raster_paths = {"model_settings": {"dem_file": "dem.tif"}}

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase._create_schematisation_base",
            return_value=(schematisation, local_schematisation, wip_revision),
        ),
        patch.object(wizard, "create_and_populate_schematisation_geopackage"),
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.SchematisationWizardBase.get_paths_from_geopackage",
            return_value=raster_paths,
        ) as get_raster_paths,
    ):
        wizard.create_new_schematisation()

    get_raster_paths.assert_called_once_with(
        str(tmp_path / "schema" / "New model.gpkg")
    )
    assert wizard.new_schematisation is schematisation
    assert wizard.new_local_schematisation is local_schematisation
    assert wizard.raster_paths == raster_paths


def test_wizard_base_resets_outputs_and_reports_build_errors(
    qgis_application, tmp_path
):
    communication = MagicMock()
    wizard = NewSchematisationWizard(
        object(),
        str(tmp_path),
        communication,
        {"owner": MagicMock()},
        "project",
        "target/",
    )
    wizard.new_schematisation = MagicMock()
    wizard.new_local_schematisation = MagicMock()
    wizard.raster_paths = {"model_settings": {"dem_file": "dem.tif"}}

    wizard.run_build(lambda: (_ for _ in ()).throw(RuntimeError("build failed")))

    assert wizard.new_schematisation is None
    assert wizard.new_local_schematisation is None
    assert wizard.raster_paths is None
    communication.bar_error.assert_called_once_with("Error: build failed")


def test_wizard_sizes_use_distinct_settings_keys():
    assert NewSchematisationWizard.SETTINGS_KEY != (
        UploadExistingSchematisationWizard.SETTINGS_KEY
    )


def test_wizard_base_rejects_name_that_exists_in_working_directory(
    qgis_application, tmp_path
):
    communication = MagicMock()
    wizard = NewSchematisationWizard(
        object(),
        str(tmp_path),
        communication,
        {"owner": MagicMock()},
        "project",
        "target/",
    )
    (tmp_path / "Existing model").mkdir()

    assert not wizard.check_name_available("Existing model")

    communication.show_error.assert_called_once()
    assert "Existing model" in communication.show_error.call_args.args[0]


def test_wizard_base_registers_remote_and_initializes_local_schematisation(
    qgis_application, tmp_path
):
    wizard = NewSchematisationWizard(
        object(),
        str(tmp_path),
        MagicMock(),
        {"owner": MagicMock()},
        "project-id",
        "target/",
    )
    local_schematisation = MagicMock()
    wip_revision = MagicMock()
    local_schematisation.wip_revision = wip_revision
    tc = MagicMock()
    tc.fetch_schematisation.return_value = MagicMock(id="schema-id")
    wizard.tc = tc

    with (
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.create_rana_schematisation",
            return_value={"schematisation_id": "schema-id"},
        ) as create_remote,
        patch(
            "rana_qgis_plugin.widgets.schematisation_new_wizard.LocalSchematisation",
            return_value=local_schematisation,
        ) as create_local,
    ):
        result = wizard._create_schematisation_base("Schema", "Description")

    create_remote.assert_called_once_with(
        project_id="project-id", path="target/Schema", description="Description"
    )
    create_local.assert_called_once_with(
        str(tmp_path),
        "schema-id",
        "Schema",
        parent_revision_number=0,
        create=True,
    )
    assert result == (
        tc.fetch_schematisation.return_value,
        local_schematisation,
        wip_revision,
    )


def test_wizard_base_persists_size_on_close(qgis_application, tmp_path):
    wizard = NewSchematisationWizard(
        object(),
        str(tmp_path),
        MagicMock(),
        {"owner": MagicMock()},
        "project",
        "target/",
    )

    with patch(
        "rana_qgis_plugin.widgets.schematisation_new_wizard.QSettings"
    ) as settings:
        wizard.done(QDialog.DialogCode.Rejected)

    settings.return_value.setValue.assert_called_once_with(
        NewSchematisationWizard.SETTINGS_KEY, wizard.size()
    )
