import csv
import os
from collections import defaultdict
from functools import partial

from qgis.core import Qgis, QgsMessageLog
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import (
    QGridLayout,
    QGroupBox,
    QLabel,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QTreeView,
    QWidget,
    QWizardPage,
)
from rana_qgis_plugin.communication import progress_bar_callback_factory
from rana_qgis_plugin.logging import LogLevels, TreeViewLogger
from rana_qgis_plugin.simulation.utils_ui import (
    get_filepath,
    migrate_schematisation_schema,
)
from rana_qgis_plugin.simulation.utils_ui import geopackage_layer


class CheckModelPage(QWizardPage):
    def __init__(
        self,
        current_local_schematisation,
        schematisation_filepath,
        communication,
        parent,
    ):
        super().__init__(parent)
        self.parent_wizard = parent
        self.main_widget = CheckModelWidget(
            self,
            current_local_schematisation,
            schematisation_filepath,
            communication,
        )
        layout = QGridLayout()
        layout.addWidget(self.main_widget, 0, 0)
        self.setLayout(layout)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.adjustSize()


class CheckModelWidget(QWidget):
    SCHEMATISATION_CHECKS_HEADER = (
        "Level",
        "Error code",
        "ID",
        "Table",
        "Column",
        "Value",
        "Description",
    )
    GRID_CHECKS_HEADER = ("Level", "Description")

    CHECKS_PER_CODE_LIMIT = 100

    def __init__(
        self,
        parent,
        current_local_schematisation,
        schematisation_filepath,
        communication,
    ):
        super().__init__(parent)

        self.setWindowTitle("Check schematisation")
        self.setMinimumSize(720, 0)

        gridLayout = QGridLayout(self)

        groupBox = QGroupBox("Schematisation Check Status", self)
        gridLayout_3 = QGridLayout(groupBox)
        gridLayout_4 = QGridLayout()
        gridLayout_4.addWidget(QLabel("GeoPackage", groupBox), 0, 0)

        self.pbar_check_schematisation = QProgressBar(groupBox)
        self.pbar_check_schematisation.setMinimumSize(0, 25)
        self.pbar_check_schematisation.setValue(0)
        gridLayout_4.addWidget(self.pbar_check_schematisation, 0, 1)

        self.lbl_check_schematisation = QLabel(groupBox)
        self.lbl_check_schematisation.setMinimumSize(0, 25)
        self.lbl_check_schematisation.setText(
            '<span style=" font-size:12pt; color:#00aa00;">✓ GeoPackage checks completed</span>'
        )
        self.lbl_check_schematisation.setAlignment(Qt.AlignCenter)
        gridLayout_4.addWidget(self.lbl_check_schematisation, 0, 2)

        self.btn_export_check_schematisation_results = QToolButton(groupBox)
        self.btn_export_check_schematisation_results.setEnabled(False)
        self.btn_export_check_schematisation_results.setMinimumSize(40, 40)
        self.btn_export_check_schematisation_results.setToolTip("Save results to CSV")
        self.btn_export_check_schematisation_results.setText("Save results to CSV")
        gridLayout_4.addWidget(self.btn_export_check_schematisation_results, 0, 3)

        gridLayout_4.addWidget(QLabel("Computational grid", groupBox), 1, 0)

        self.pbar_check_grid = QProgressBar(groupBox)
        self.pbar_check_grid.setMinimumSize(0, 25)
        self.pbar_check_grid.setValue(0)
        gridLayout_4.addWidget(self.pbar_check_grid, 1, 1)

        self.lbl_check_grid = QLabel(groupBox)
        self.lbl_check_grid.setText(
            '<span style=" font-size:12pt; color:#00aa00;">✓ Computational grid checks completed</span>'
        )
        self.lbl_check_grid.setAlignment(Qt.AlignCenter)
        self.lbl_check_grid.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)
        gridLayout_4.addWidget(self.lbl_check_grid, 1, 2)

        self.btn_export_check_grid_results = QToolButton(groupBox)
        self.btn_export_check_grid_results.setEnabled(False)
        self.btn_export_check_grid_results.setMinimumSize(40, 40)
        self.btn_export_check_grid_results.setToolTip("Save results to CSV")
        self.btn_export_check_grid_results.setText("Save results to CSV")
        gridLayout_4.addWidget(self.btn_export_check_grid_results, 1, 3)

        gridLayout_3.addLayout(gridLayout_4, 0, 1)
        gridLayout.addWidget(groupBox, 0, 0)

        gridLayout.addWidget(QLabel("Schematisation checks outcome:", self), 1, 0)

        self.tv_schema_check_result = QTreeView(self)
        self.tv_schema_check_result.setEditTriggers(QTreeView.NoEditTriggers)
        self.tv_schema_check_result.setSelectionMode(QTreeView.ExtendedSelection)
        self.tv_schema_check_result.setSortingEnabled(True)
        gridLayout.addWidget(self.tv_schema_check_result, 2, 0)

        gridLayout.addWidget(QLabel("Computational grid checks outcome:", self), 3, 0)

        self.tv_grid_check_result = QTreeView(self)
        self.tv_grid_check_result.setEditTriggers(QTreeView.NoEditTriggers)
        gridLayout.addWidget(self.tv_grid_check_result, 4, 0)

        gridLayout_2 = QGridLayout()
        gridLayout_2.setContentsMargins(0, 0, 0, 0)

        self.lbl_on_limited_display = QLabel(self)
        self.lbl_on_limited_display.setWordWrap(True)
        self.lbl_on_limited_display.setText(
            "⚠Not all messages are displayed. Schematisation checker results are limited to the 100 per error code."
        )
        gridLayout_2.addWidget(self.lbl_on_limited_display, 0, 0, 1, 2)

        self.lbl_on_import_error = QLabel(self)
        self.lbl_on_import_error.setWordWrap(True)
        self.lbl_on_import_error.setText(
            "⚠Cannot check schematisation. Please make sure 3Di Results Analysis is installed and activated to fix this."
        )
        gridLayout_2.addWidget(self.lbl_on_import_error, 1, 0, 1, 2)

        self.pb_check_model = QPushButton("Check schematisation", self)
        gridLayout_2.addWidget(self.pb_check_model, 2, 1)

        gridLayout.addLayout(gridLayout_2, 5, 0)

        self.current_local_schematisation = current_local_schematisation
        self.schematisation_filepath = schematisation_filepath
        self.communication = communication

        self.schematisation_checker_logger = TreeViewLogger(
            self.tv_schema_check_result, self.SCHEMATISATION_CHECKS_HEADER
        )
        self.grid_checker_logger = TreeViewLogger(
            self.tv_grid_check_result, self.GRID_CHECKS_HEADER
        )

        self.pb_check_model.clicked.connect(self.run_model_checks)

        self.btn_export_check_schematisation_results.clicked.connect(
            partial(
                self.export_schematisation_checker_results,
                self.schematisation_checker_logger,
                self.SCHEMATISATION_CHECKS_HEADER,
            )
        )
        self.btn_export_check_grid_results.clicked.connect(
            partial(
                self.export_schematisation_checker_results,
                self.grid_checker_logger,
                self.GRID_CHECKS_HEADER,
            )
        )
        self.lbl_check_schematisation.hide()
        self.lbl_check_grid.hide()
        self.lbl_on_limited_display.hide()
        self.test_external_imports()

    def test_external_imports(self):
        """Check availability of an external checkers."""
        try:
            from sqlalchemy.exc import OperationalError
            from threedi_modelchecker import ThreediModelChecker
            from threedi_schema import ThreediDatabase, errors
            from threedigrid_builder import SchematisationError, make_gridadmin

            self.lbl_on_import_error.hide()
            self.pb_check_model.setEnabled(True)
        except ImportError:
            self.lbl_on_import_error.show()
            self.pb_check_model.setDisabled(True)

    def run_model_checks(self):
        """Run all available checks for a schematisation model."""
        self.btn_export_check_schematisation_results.setDisabled(True)
        self.lbl_check_schematisation.hide()
        self.pbar_check_schematisation.show()
        self.schematisation_checker_logger.initialize_view()
        self.pbar_check_schematisation.setValue(0)
        self.check_schematisation()
        self.btn_export_check_schematisation_results.setEnabled(True)
        self.lbl_check_grid.hide()
        self.pbar_check_grid.show()
        self.grid_checker_logger.initialize_view()
        self.pbar_check_grid.setValue(0)
        self.check_computational_grid()
        self.btn_export_check_grid_results.setEnabled(True)
        self.communication.bar_info("Finished schematisation checks.")

    def check_schematisation(self):
        """Run schematisation database checks."""
        from sqlalchemy.exc import OperationalError
        from threedi_modelchecker import ThreediModelChecker
        from threedi_schema import ThreediDatabase, errors

        self.lbl_on_limited_display.hide()
        threedi_db = ThreediDatabase(self.schematisation_filepath)
        schema = threedi_db.schema
        try:
            schema.validate_schema()
        except errors.MigrationMissingError:
            warn_and_ask_msg = (
                "The selected schematisation DB cannot be used, because its database schema version is out of date. "
                "Would you like to migrate your schematisation database to the current schema version?"
            )
            do_migration = self.communication.ask(
                None, "Missing migration", warn_and_ask_msg
            )
            if not do_migration:
                self.communication.bar_warn("Schematisation checks skipped!")
                return
            wip_revision = self.current_local_schematisation.wip_revision
            QCoreApplication.processEvents()
            migration_info = "Schema migration..."
            self.communication.progress_bar(
                migration_info, 0, 100, 0, clear_msg_bar=True
            )

            progress_bar_callback = None
            progress_bar_callback = progress_bar_callback_factory(self.communication)
            migration_succeed, migration_feedback_msg = migrate_schematisation_schema(
                wip_revision.schematisation_db_filepath, progress_bar_callback
            )

            self.communication.progress_bar(
                "Migration complete!", 0, 100, 100, clear_msg_bar=True
            )
            QCoreApplication.processEvents()
            self.communication.clear_message_bar()

            # Something is wrong here - check this logic!!!
            if migration_succeed and len(migration_feedback_msg) > 0:
                self.communication.show_info(migration_feedback_msg, self, "Export")
                QgsMessageLog.logMessage(
                    migration_feedback_msg, level=Qgis.Warning, tag="Messages"
                )
            elif not migration_succeed:
                self.communication.show_error(migration_feedback_msg, self)
                return
            threedi_db = ThreediDatabase(
                self.schematisation_filepath.rsplit(".", 1)[0] + ".gpkg"
            )
        except Exception as e:
            error_msg = f"{e}"
            self.communication.show_error(error_msg, self)
            return
        try:
            model_checker = ThreediModelChecker(threedi_db)
            model_checker.db.check_connection()
        except OperationalError as exc:
            error_msg = (
                f"Failed to start a connection with the database.\n"
                f"Something went wrong trying to connect to the database, "
                f"please check the connection settings: {exc.args[0]}"
            )
            self.communication.show_error(error_msg, self)
            return

        session = model_checker.db.get_session()
        session.model_checker_context = model_checker.context
        total_checks = len(model_checker.config.checks)

        results_rows = defaultdict(list)
        for i, check in enumerate(
            model_checker.checks(level=LogLevels.INFO.value), start=1
        ):
            for result_row in check.get_invalid(session):
                results_rows[check.error_code].append(
                    [
                        check.level.name,
                        check.error_code,
                        result_row.id,
                        check.table.name,
                        check.column.name,
                        getattr(result_row, check.column.name),
                        check.description(),
                    ]
                )
            self.pbar_check_schematisation.setValue(i)
        if results_rows:
            for error_code, results_per_code in results_rows.items():
                if len(results_per_code) > self.CHECKS_PER_CODE_LIMIT:
                    results_per_code = results_per_code[: self.CHECKS_PER_CODE_LIMIT]
                    if self.lbl_on_limited_display.isHidden():
                        self.lbl_on_limited_display.show()
                for result_row in results_per_code:
                    level = result_row[0].upper()
                    self.schematisation_checker_logger.log_result_row(result_row, level)
        self.pbar_check_schematisation.setValue(total_checks)
        self.pbar_check_schematisation.hide()
        self.lbl_check_schematisation.show()

    def check_computational_grid(self):
        """Run computational grid checks."""
        from threedigrid_builder import SchematisationError, make_gridadmin

        def progress_logger(progress, info):
            self.pbar_check_grid.setValue(int(progress * 100))
            self.grid_checker_logger.log_result_row(
                [LogLevels.INFO.value.capitalize(), info], LogLevels.INFO.value
            )

        self.pbar_check_grid.setMaximum(100)
        self.pbar_check_grid.setValue(0)
        try:
            model_settings_layer = geopackage_layer(
                self.schematisation_filepath, "model_settings"
            )
            model_settings_feat = next(model_settings_layer.getFeatures())
            dem_file = model_settings_feat["dem_file"]
            if dem_file:
                schematisation_dir = os.path.dirname(self.schematisation_filepath)
                dem_file_name = os.path.basename(dem_file)
                dem_path = os.path.join(schematisation_dir, "rasters", dem_file_name)
            else:
                dem_path = None

            make_gridadmin(
                sqlite_path=self.schematisation_filepath,
                dem_path=dem_path,
                progress_callback=progress_logger,
            )
        except SchematisationError as e:
            err = f"Creating grid file failed with the following error: {repr(e)}"
            self.grid_checker_logger.log_result_row(
                [LogLevels.ERROR.value.capitalize(), err], LogLevels.ERROR.value
            )
        except Exception as e:
            err = f"Checking computational grid failed with the following error: {repr(e)}"
            self.grid_checker_logger.log_result_row(
                [LogLevels.ERROR.value.capitalize(), err], LogLevels.ERROR.value
            )
        finally:
            self.pbar_check_grid.setValue(100)
        self.pbar_check_grid.hide()
        self.lbl_check_grid.show()

    def export_schematisation_checker_results(self, logger_tree_view, header):
        """Save schematisation checker results into the CSV file."""
        model = logger_tree_view.model
        row_count = model.rowCount()
        column_count = model.columnCount()
        checker_results = []
        for row_idx in range(row_count):
            row_items = [
                model.item(row_idx, col_idx) for col_idx in range(column_count)
            ]
            row = [it.text() for it in row_items]
            checker_results.append(row)
        if not checker_results:
            self.communication.show_warn(
                "There is nothing to export. Action aborted.", self, "Warning"
            )
            return
        csv_filepath = get_filepath(
            self,
            extension_filter="CSV file (*.csv)",
            save=True,
            dialog_title="Export schematisation checker results",
        )
        if not csv_filepath:
            return
        with open(csv_filepath, "w", newline="") as csv_file:
            csv_writer = csv.writer(csv_file, delimiter=",")
            csv_writer.writerow(header)
            csv_writer.writerows(checker_results)
        self.communication.show_info(
            "Schematisation checker results successfully exported!", self, "Export"
        )
