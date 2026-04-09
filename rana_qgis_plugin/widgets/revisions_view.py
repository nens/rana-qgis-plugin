from collections import namedtuple

from qgis.PyQt.QtCore import Qt, pyqtSignal
from qgis.PyQt.QtGui import (
    QAction,
    QStandardItem,
    QStandardItemModel,
)
from qgis.PyQt.QtWidgets import (
    QHeaderView,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls
from rana_qgis_plugin.utlis.api import (
    get_tenant_project_file_history,
    get_threedi_schematisation,
)
from rana_qgis_plugin.utlis.generic import NumericItem, get_threedi_api
from rana_qgis_plugin.utlis.time import get_timestamp_as_numeric_item


class RevisionsView(QWidget):
    new_simulation_clicked = pyqtSignal(int)
    create_3di_model_clicked = pyqtSignal(int)
    delete_3di_model_clicked = pyqtSignal(int)
    open_schematisation_revision_in_qgis_requested = pyqtSignal(dict, dict)
    export_schematisation_revision = pyqtSignal(dict, dict)
    busy = pyqtSignal()
    ready = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self.revisions = []
        self.selected_file = None
        self.project = None
        self.setup_ui()

    def setup_ui(self):
        self.revisions_table = QTableView()
        self.revisions_table.setSortingEnabled(True)
        self.revisions_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.revisions_table.verticalHeader().hide()
        self.revisions_model = QStandardItemModel()
        self.revisions_table.setModel(self.revisions_model)
        self.revisions_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.Stretch
        )
        self.revisions_table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu
        )
        self.revisions_table.customContextMenuRequested.connect(self.menu_requested)
        self.revisions_table.setShowGrid(False)
        self.revisions_table.horizontalHeader().setFrameStyle(0)
        layout = QVBoxLayout(self)
        layout.addWidget(self.revisions_table)
        self.setLayout(layout)

    def show_revisions_for_file(self, project: dict, selected_file: dict):
        self.project = project
        self.selected_file = selected_file
        self.show_revisions()

    def menu_requested(self, pos):
        index = self.revisions_table.indexAt(pos)
        revision_item = self.revisions_model.itemFromIndex(index)
        if not revision_item:
            return
        data = revision_item.data()
        if not data:
            return
        threedi_revision, schematisation = data
        if threedi_revision:
            menu = QMenu(self)
            action = QAction("Open in QGIS", self)
            action.triggered.connect(
                lambda _: self.open_schematisation_revision_in_qgis_requested.emit(
                    threedi_revision.to_dict(), schematisation["schematisation"]
                )
            )
            menu.addAction(action)
            action = QAction("Export as geopackage", self)
            action.triggered.connect(
                lambda _: self.export_schematisation_revision.emit(
                    schematisation["schematisation"], threedi_revision.to_dict()
                )
            )
            menu.addAction(action)

        menu.popup(self.revisions_table.viewport().mapToGlobal(pos))

    def refresh(self):
        self.show_revisions()

    def show_revisions(self):
        self.busy.emit()
        selected_file = self.selected_file
        # collect rows to show in widget, format: [date_str, event, (button_label, signal_func), revision, schematisation]
        rows = []
        BTNData = namedtuple("BTNData", ["label", "func", "enabled", "tooltip"])
        if selected_file.get("data_type") == "threedi_schematisation":
            # retrieve schematisation and revisions
            schematisation = get_threedi_schematisation(
                self.communication, selected_file["descriptor_id"]
            )
            threedi_api = get_threedi_api()
            tc = ThreediCalls(threedi_api)
            revisions = tc.fetch_schematisation_revisions(
                schematisation["schematisation"]["id"]
            )
            # Check number of models and enable creation if max has been reached
            create_enabled = True
            create_tooltip = None
            if (
                sum(revision.has_threedimodel for revision in revisions)
                >= schematisation["schematisation"]["threedimodel_limit"]
            ):
                create_enabled = False
                create_tooltip = "The maximum number of Rana models has been reached. Please delete one of the existing models before creating a new one."
            # Extract data from each revision
            for i, revision in enumerate(revisions):
                commit_date = revision.commit_date.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                latest = revision.id == schematisation["latest_revision"]["id"]
                tooltip = (
                    "A Rana model must be created before a simulation can be started."
                    if not revision.has_threedimodel
                    else None
                )
                sim_btn_data = BTNData(
                    "New",
                    lambda _, rev_id=revision.id: self.new_simulation_clicked.emit(
                        rev_id
                    ),
                    revision.has_threedimodel,
                    tooltip,
                )
                if revision.has_threedimodel:
                    model_btn_data = BTNData(
                        "Delete",
                        lambda _,
                        rev_id=revision.id: self.delete_3di_model_clicked.emit(rev_id),
                        True,
                        None,
                    )
                else:
                    model_btn_data = BTNData(
                        "Create",
                        lambda _,
                        rev_id=revision.id: self.create_3di_model_clicked.emit(rev_id),
                        create_enabled,
                        create_tooltip,
                    )
                rows.append(
                    [
                        commit_date,
                        revision.commit_message,
                        sim_btn_data,
                        model_btn_data,
                        revision,
                        schematisation,
                        latest,
                    ]
                )
        else:
            history = get_tenant_project_file_history(
                self.project["id"], {"path": self.selected_file["id"]}
            )
            for item in history["items"]:
                rows.append([item["created_at"], item["message"]])

        # Populate table
        self.revisions_model.clear()
        if selected_file.get("data_type") == "threedi_schematisation":
            self.revisions_model.setColumnCount(5)
            self.revisions_model.setHorizontalHeaderLabels(
                ["#", "Timestamp", "Event", "Simulation", "Rana Model"]
            )
        else:
            self.revisions_model.setColumnCount(2)
            self.revisions_model.setHorizontalHeaderLabels(["Timestamp", "Event"])
        latest = False
        threedi_revision = sim_btn_data = model_btn_data = threedi_schematisation = None
        for i, (commit_date, event, *schematisation_related) in enumerate(rows):
            row = []
            if schematisation_related:
                (
                    sim_btn_data,
                    model_btn_data,
                    threedi_revision,
                    threedi_schematisation,
                    latest,
                ) = schematisation_related
                nr_item = NumericItem(str(threedi_revision.number))
                nr_item.setData(threedi_revision.number, role=Qt.ItemDataRole.UserRole)
                row.append(nr_item)
            commit_item = get_timestamp_as_numeric_item(commit_date)
            if latest:
                commit_item.setText(commit_item.text() + " (latest)")
            # We store the revision object for loading specific revisions in menu_requested.
            if threedi_revision:
                commit_item.setData((threedi_revision, threedi_schematisation))
            row += [commit_item, QStandardItem(event)]
            self.revisions_model.appendRow(row)
            for col_idx, btn_data in enumerate([sim_btn_data, model_btn_data], 3):
                if btn_data:
                    btn = QPushButton(btn_data.label)
                    btn.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    btn.clicked.connect(btn_data.func)
                    btn.setEnabled(btn_data.enabled)
                    if btn_data.tooltip:
                        btn.setToolTip(btn_data.tooltip)
                    container = QWidget()
                    container.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
                    layout = QVBoxLayout(container)
                    layout.setContentsMargins(0, 0, 0, 0)
                    layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
                    layout.addWidget(btn)
                    container.adjustSize()
                    self.revisions_table.setIndexWidget(
                        self.revisions_model.index(i, col_idx), container
                    )

        if threedi_revision:
            resize_columns = [0, 1, 3, 4]
        else:
            resize_columns = [0]
        for col_idx in resize_columns:
            self.revisions_table.horizontalHeader().setSectionResizeMode(
                col_idx, QHeaderView.ResizeToContents
            )
        self.ready.emit()
