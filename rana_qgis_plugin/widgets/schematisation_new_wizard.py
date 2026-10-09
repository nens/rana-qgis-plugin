import os
import shutil
import time
from collections import defaultdict
from pathlib import Path

from qgis.core import QgsFeature
from qgis.PyQt.QtCore import QSettings, QSize
from qgis.PyQt.QtWidgets import QApplication, QSizePolicy, QWizard
from threedi_api_client.openapi import ApiException
from threedi_mi_utils import LocalSchematisation
from threedi_schema import ThreediDatabase

from rana_qgis_plugin.simulation.threedi_calls import (
    SchematisationApiMapper,
    ThreediCalls,
)
from rana_qgis_plugin.simulation.utils import (
    extract_error_message,
    geopackage_layer,
)
from rana_qgis_plugin.simulation.utils_ui import ensure_valid_schema
from rana_qgis_plugin.utils.api import RanaPostError, create_rana_schematisation
from rana_qgis_plugin.widgets.new_wizard_pages.explain import (
    SchematisationExplainPage,
)
from rana_qgis_plugin.widgets.new_wizard_pages.name import (
    SchematisationNamePage,
)
from rana_qgis_plugin.widgets.new_wizard_pages.settings import (
    SchematisationSettingsPage,
)


class CommitErrors(Exception):
    pass


class GeoPackageError(Exception):
    pass


def check_name_available(name, working_dir, communication):
    """Check if schematisation name is available in the working directory.

    Returns True if available, False if not (and shows an error).
    """
    if (Path(working_dir) / name).exists():
        communication.show_error(
            f"Schematisation with name {name} already exists in working directory. Please choose a different name and try again."
        )
        return False
    return True


def _create_schematisation_base(
    tc, working_dir, name, owner, description, project_id, rana_path
):
    """Create schematisation via Rana and set up local directory structure.

    Returns a tuple of (schematisation, local_schematisation, wip_revision).
    """
    path = f"{rana_path}{name}" if rana_path else name
    rana_response = create_rana_schematisation(
        project_id=project_id, path=path, description=description
    )
    schematisation = tc.fetch_schematisation(rana_response["schematisation_id"])
    local_schematisation = LocalSchematisation(
        working_dir,
        rana_response["schematisation_id"],
        name,
        parent_revision_number=0,
        create=True,
    )
    wip_revision = local_schematisation.wip_revision
    return schematisation, local_schematisation, wip_revision


class NewSchematisationWizard(QWizard):
    """New schematisation wizard."""

    def __init__(
        self,
        threedi_api,
        working_dir,
        communication,
        organisations,
        project_id,
        rana_path,
    ):
        super().__init__()
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.working_dir = working_dir
        self.threedi_api = threedi_api
        self.tc = ThreediCalls(threedi_api)
        self.communication = communication
        self.project_id = project_id
        self.rana_path = rana_path
        self.raster_paths = None
        self.new_schematisation = None
        self.new_local_schematisation = None
        self.available_organisations = organisations

        self.schematisation_name_page = SchematisationNamePage(
            self.available_organisations, self
        )
        self.schematisation_explain_page = SchematisationExplainPage(self)
        self.schematisation_settings_page = SchematisationSettingsPage(
            self.communication, self
        )
        self.addPage(self.schematisation_name_page)
        self.addPage(self.schematisation_explain_page)
        self.addPage(self.schematisation_settings_page)
        self.setButtonText(QWizard.WizardButton.FinishButton, "Create schematisation")
        self.finish_btn = self.button(QWizard.WizardButton.FinishButton)
        self.finish_btn.clicked.connect(self.create_schematisation)
        self.cancel_btn = self.button(QWizard.WizardButton.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.setWindowTitle("New schematisation")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setOption(QWizard.WizardOption.HaveNextButtonOnLastPage, False)
        self.resize(
            QSettings().value("threedi/new_schematisation_wizard_size", QSize(790, 700))
        )

    @staticmethod
    def create_and_populate_schematisation_geopackage(
        geopackage_filepath: str | Path,
        schematisation_settings: dict,
        raster_filepaths: tuple[str, str],
        raster_dir: str | Path,
        communication,
    ) -> None:
        """Initialize and populate a schematisation GeoPackage from collected settings."""
        database = ThreediDatabase(str(geopackage_filepath))

        # A new empty database must first be upgraded to the first schema revision.
        def feedback_callback_factory(communication):
            """Callback function to track schematisation migration progress."""

            def feedback_callback(progress, message):
                communication.progress_bar(
                    msg=message,
                    minimum=0,
                    maximum=100,
                    init_value=int(progress),
                    clear_msg_bar=True,
                )
                QApplication.processEvents()

            return feedback_callback

        database.schema.upgrade(revision="0200")
        database.schema.upgrade(
            progress_func=feedback_callback_factory(communication),
            epsg_code_override=schematisation_settings["model_settings"]["epsg_code"],
        )

        for raster_filepath in raster_filepaths:
            if raster_filepath:
                raster_path = Path(raster_filepath)
                shutil.copyfile(raster_path, Path(raster_dir) / raster_path.name)

        for table_name, table_settings in schematisation_settings.items():
            table_layer = geopackage_layer(str(geopackage_filepath), table_name)
            table_layer.startEditing()
            table_fields = table_layer.fields()
            table_field_names = {field.name() for field in table_fields}
            first_value = next(iter(table_settings.values()), None)
            row_count = len(first_value) if isinstance(first_value, list) else 1
            for row_index in range(row_count):
                feature = QgsFeature(table_fields)
                for field_name, field_value in table_settings.items():
                    if field_name not in table_field_names:
                        continue
                    feature[field_name] = (
                        field_value[row_index]
                        if isinstance(field_value, list)
                        else field_value
                    )
                table_layer.addFeature(feature)
            if not table_layer.commitChanges():
                errors = "\n".join(table_layer.commitErrors())
                raise CommitErrors(f"{table_name} commit errors:\n{errors}")

    def create_schematisation(self):
        name = self.schematisation_name_page.name
        if not check_name_available(name, self.working_dir, self.communication):
            return
        self.create_new_schematisation()

    def create_new_schematisation(self):
        """Get settings from the wizard and create new schematisation (locally and remotely)."""
        if not self.schematisation_settings_page.settings_are_valid:
            return

        name = self.schematisation_name_page.name
        description = self.schematisation_name_page.description
        owner = self.schematisation_name_page.owner

        schematisation_settings = self.schematisation_settings_page.main_widget.collect_new_schematisation_settings()
        raster_filepaths = (
            self.schematisation_settings_page.main_widget.raster_filepaths()
        )
        try:
            schematisation, local_schematisation, wip_revision = (
                _create_schematisation_base(
                    self.tc,
                    self.working_dir,
                    name,
                    owner,
                    description,
                    self.project_id,
                    self.rana_path,
                )
            )

            schematisation_filename = f"{name}.gpkg"
            geopackage_filepath = os.path.join(
                wip_revision.schematisation_dir, schematisation_filename
            )

            self.create_and_populate_schematisation_geopackage(
                geopackage_filepath,
                schematisation_settings,
                raster_filepaths,
                wip_revision.raster_dir,
                self.communication,
            )
            self.raster_paths = (
                UploadExistingSchematisationWizard.get_paths_from_geopackage(
                    geopackage_filepath
                )
            )
            time.sleep(0.5)
            self.new_schematisation = schematisation
            self.new_local_schematisation = local_schematisation
            msg = f"Schematisation '{name} ({schematisation.id})' created!"
            self.communication.bar_info(msg)
        except (ApiException, RanaPostError) as e:
            self.raster_paths = None
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = extract_error_message(e)
            self.communication.bar_error(error_msg)
        except Exception as e:
            self.raster_paths = None
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        QSettings().setValue("threedi/new_schematisation_wizard_size", self.size())
        self.reject()


class UploadExistingSchematisationWizard(QWizard):
    """Wizard for creating a new schematisation from an existing GeoPackage."""

    def __init__(
        self,
        threedi_api,
        working_dir,
        communication,
        organisations,
        gpkg_path,
        project_id,
        rana_path,
    ):
        super().__init__()
        self.setWizardStyle(QWizard.WizardStyle.ClassicStyle)
        self.working_dir = working_dir
        self.threedi_api = threedi_api
        self.tc = ThreediCalls(threedi_api)
        self.communication = communication
        self.gpkg_path = gpkg_path
        self.project_id = project_id
        self.rana_path = rana_path
        self.raster_paths = None
        self.new_schematisation = None
        self.new_local_schematisation = None
        self.available_organisations = organisations

        self.schematisation_name_page = SchematisationNamePage(
            self.available_organisations, self
        )
        self.schematisation_name_page.setFinalPage(True)
        self.addPage(self.schematisation_name_page)
        self.setButtonText(QWizard.WizardButton.FinishButton, "Create schematisation")
        self.finish_btn = self.button(QWizard.WizardButton.FinishButton)
        self.finish_btn.clicked.connect(self.create_schematisation)
        self.cancel_btn = self.button(QWizard.WizardButton.CancelButton)
        self.cancel_btn.clicked.connect(self.cancel_wizard)
        self.setWindowTitle("Upload existing schematisation")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setButtonLayout(
            [
                QWizard.WizardButton.Stretch,
                QWizard.WizardButton.FinishButton,
                QWizard.WizardButton.CancelButton,
            ]
        )
        self.resize(
            QSettings().value("threedi/new_schematisation_wizard_size", QSize(790, 700))
        )

    @staticmethod
    def get_paths_from_geopackage(geopackage_path):
        """Search GeoPackage database tables for attributes with file paths."""
        paths: defaultdict[str, dict] = defaultdict(dict)
        for (
            table_name,
            raster_info,
        ) in SchematisationApiMapper.raster_reference_tables().items():
            settings_fields = list(raster_info.keys())
            settings_lyr = geopackage_layer(geopackage_path, table_name)
            if not settings_lyr.isValid():
                raise GeoPackageError(
                    f"'{table_name}' table could not be loaded from {geopackage_path}"
                )
            try:
                set_feat = next(settings_lyr.getFeatures())
            except StopIteration:
                continue
            for field_name in settings_fields:
                field_value = set_feat[field_name]
                paths[table_name][field_name] = field_value if field_value else None
        return paths

    @staticmethod
    def prepare_existing_schematisation(source_path, communication):
        """Validate an existing input and resolve its GeoPackage and raster references."""
        source_path = Path(source_path)
        if not ensure_valid_schema(str(source_path), communication):
            return None

        geopackage_path = (
            source_path.with_suffix(".gpkg")
            if source_path.suffix.lower() == ".sqlite"
            else source_path
        )
        if not geopackage_path.is_file():
            communication.show_error(
                f"Expected GeoPackage was not found: {geopackage_path}"
            )
            return None

        try:
            raster_paths = UploadExistingSchematisationWizard.get_paths_from_geopackage(
                str(geopackage_path)
            )
        except GeoPackageError as error:
            communication.show_error(str(error))
            return None

        raster_directory = source_path.parent / "rasters"
        missing_rasters = [
            (field_name, relative_path)
            for table_rasters in raster_paths.values()
            for field_name, relative_path in table_rasters.items()
            if relative_path and not (raster_directory / relative_path).is_file()
        ]
        if missing_rasters:
            missing_rasters.sort(key=lambda raster: raster[0])
            missing = "\n".join(
                f"{field_name}: {relative_path}"
                for field_name, relative_path in missing_rasters
            )
            communication.show_warn(
                f"The following referenced raster files were not found:\n{missing}"
            )
            return None

        return geopackage_path, raster_paths

    @staticmethod
    def copy_existing_schematisation_content(
        geopackage_path, raster_paths, name, wip_revision
    ):
        """Copy a validated GeoPackage and its referenced rasters into a local WIP."""
        geopackage_destination = Path(wip_revision.schematisation_dir) / f"{name}.gpkg"
        shutil.copyfile(geopackage_path, geopackage_destination)
        for table_rasters in raster_paths.values():
            for relative_path in table_rasters.values():
                if relative_path:
                    raster_path = (
                        Path(geopackage_path).parent / "rasters" / relative_path
                    )
                    shutil.copyfile(
                        raster_path, Path(wip_revision.raster_dir) / raster_path.name
                    )

    def create_schematisation(self):
        """Create a new schematisation from the provided GeoPackage."""
        name = self.schematisation_name_page.name
        if not check_name_available(name, self.working_dir, self.communication):
            return

        description = self.schematisation_name_page.description
        owner = self.schematisation_name_page.owner

        try:
            prepared_input = self.prepare_existing_schematisation(
                self.gpkg_path, self.communication
            )
            if prepared_input is None:
                return
            src_db, raster_paths = prepared_input
            self.raster_paths = raster_paths

            schematisation, local_schematisation, wip_revision = (
                _create_schematisation_base(
                    self.tc,
                    self.working_dir,
                    name,
                    owner,
                    description,
                    self.project_id,
                    self.rana_path,
                )
            )
            self.copy_existing_schematisation_content(
                src_db, raster_paths, name, wip_revision
            )
            self.new_schematisation = schematisation
            self.new_local_schematisation = local_schematisation
            msg = f"Schematisation '{name} ({schematisation.id})' created!"
            self.communication.bar_info(msg)
        except (ApiException, RanaPostError) as e:
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = extract_error_message(e)
            self.communication.bar_error(error_msg)
        except Exception as e:
            self.raster_paths = None
            self.new_schematisation = None
            self.new_local_schematisation = None
            error_msg = f"Error: {e}"
            self.communication.bar_error(error_msg)

    def cancel_wizard(self):
        """Handling canceling wizard action."""
        QSettings().setValue("threedi/new_schematisation_wizard_size", self.size())
        self.reject()
