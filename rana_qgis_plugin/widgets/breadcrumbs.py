from collections import namedtuple
from enum import Enum
from typing import List

from qgis.PyQt.QtCore import (
    QSize,
    Qt,
    pyqtSignal,
)
from qgis.PyQt.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStackedWidget,
    QWidget,
)

from rana_qgis_plugin.icons import ellipsis_icon, separator_icon
from rana_qgis_plugin.utils import elide_text


class BreadcrumbType(Enum):
    PROJECTS = "projects"
    FOLDER = "folder"
    FILE = "file"
    REVISIONS = "revisions"
    PROJECT = "project"


BreadcrumbItem = namedtuple("BreadcrumbItem", ["type", "name"])


class BreadcrumbsWidget(QWidget):
    projects_selected = pyqtSignal()
    folder_selected = pyqtSignal(str)
    file_selected = pyqtSignal()

    def __init__(self, communication, parent=None):
        super().__init__(parent)
        self.communication = communication
        self._items: List[BreadcrumbItem] = [
            BreadcrumbItem(BreadcrumbType.PROJECTS, "Projects")
        ]
        self.setup_ui()
        self.update()

    def setup_ui(self):
        self.layout = QHBoxLayout(self)
        self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.create_ellipsis()
        self.setLayout(self.layout)

    def back_to_root(self):
        self._items = self._items[:1]
        self.update()

    def create_ellipsis(self):
        # when deleting and creating this widget on-the-fly qgis crashes with a segfault
        # to avoid this, it is created on ui setup, and just shown and hidden instead
        self.ellipsis = QPushButton()
        self.ellipsis.setIcon(ellipsis_icon)
        self.ellipsis.setIconSize(QSize(20, 20))
        self.ellipsis.setStyleSheet(
            "QPushButton::menu-indicator{ image: url(none.jpg); }"
        )
        context_menu = QMenu()
        self.ellipsis.setMenu(context_menu)
        self.ellipsis.hide()

    def clear(self):
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                self.layout.removeWidget(widget)
                if widget == self.ellipsis:
                    self.ellipsis.hide()
                else:
                    widget.deleteLater()

    def get_button(self, index: int, item: BreadcrumbItem) -> QLabel:
        label_text = elide_text(self.font(), item.name, 100)
        # Last item cannot be clicked
        if index == len(self._items) - 1:
            label = QLabel(f"<b>{label_text}</b>")
            label.setTextFormat(Qt.TextFormat.RichText)
        else:
            link = f"<a href='{index}'>{label_text}</a>"
            label = QLabel(link)
            label.setTextFormat(Qt.TextFormat.RichText)
            label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
            label.linkActivated.connect(lambda _, idx=index: self.on_click(idx))
        label.setToolTip(item.name)
        return label

    def _add_separator(self):
        separator_pixmap = separator_icon.pixmap(QSize(16, 16))
        separator = QLabel()
        separator.setPixmap(separator_pixmap)
        self.layout.addWidget(separator)

    def add_path_widgets(
        self, items, leading_separator=False, trailing_separator=False
    ):
        if leading_separator:
            self._add_separator()
        for i, item in items:
            label = self.get_button(i, item)
            self.layout.addWidget(label)
            if (i != items[-1][0]) or trailing_separator:
                self._add_separator()

    def add_path_dropdown_widget(self, items):
        self.layout.addWidget(self.ellipsis)
        self.ellipsis.show()
        context_menu = self.ellipsis.menu()
        context_menu.clear()
        for index, item in items:
            item_text = elide_text(self.font(), item.name, 100)
            context_menu.addAction(item_text, lambda idx=index: self.on_click(idx))

    def update(self):
        self.clear()
        numbered_items = [[i, item] for i, item in enumerate(self._items)]
        if len(self._items) >= 6:
            # with dropdown
            before_dropdown_items = numbered_items[:2]
            dropdown_items = numbered_items[2:-2]
            after_dropdown_items = numbered_items[-2:]
            self.add_path_widgets(before_dropdown_items, trailing_separator=True)
            self.add_path_dropdown_widget(dropdown_items)
            self.add_path_widgets(after_dropdown_items, leading_separator=True)
        else:
            # without dropdown
            self.add_path_widgets(numbered_items)

    def on_click(self, index: int):
        # Truncate items to clicked position
        self._items = self._items[: index + 1]
        if index == 0:  # Projects
            self.projects_selected.emit()
        else:
            self.communication.progress_bar("Loading files...", clear_msg_bar=True)
            clicked_item = self._items[index]
            if clicked_item.type == BreadcrumbType.FILE:
                self.file_selected.emit()
            else:
                # path should be None for project root
                if len(self._items) == 2:
                    path = None
                else:
                    path = "/".join(item.name for item in self._items[2:]) + "/"
                self.folder_selected.emit(path)
            self.communication.clear_message_bar()
        self.update()


class FilesBreadcrumbsWidget(BreadcrumbsWidget):
    """Breadcrumbs widget specialized for file tab"""

    def remove_file(self):
        # remove last item from the path
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items.pop()
        self.update()

    def rename_file(self, new_name):
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items[-1] = BreadcrumbItem(BreadcrumbType.FILE, new_name)
        self.update()

    def add_file(self, file_path):
        # files can only be added after a folder
        if self._items[-1].type == BreadcrumbType.FOLDER:
            self._items.append(BreadcrumbItem(BreadcrumbType.FILE, file_path))
        self.update()

    def add_folder(self, folder_name):
        # folders can only be added after projects or a folder
        if self._items[-1].type in [BreadcrumbType.PROJECTS, BreadcrumbType.FOLDER]:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, folder_name))
        self.update()

    def add_revisions(self, selected_file):
        # revisions can only be added after a file
        if self._items[-1].type == BreadcrumbType.FOLDER:
            self.add_file(selected_file["id"])
        if self._items[-1].type == BreadcrumbType.FILE:
            self._items.append(BreadcrumbItem(BreadcrumbType.REVISIONS, "Revisions"))
        self.update()

    def set_folders(self, paths):
        for item in paths:
            self._items.append(BreadcrumbItem(BreadcrumbType.FOLDER, item))
        self.update()


class GenericBreadcrumbsWidget(BreadcrumbsWidget):
    def add_project(self, project_name):
        # folders can only be added after projects or a folder
        if self._items[-1].type in [BreadcrumbType.PROJECTS]:
            self._items.append(BreadcrumbItem(BreadcrumbType.PROJECT, project_name))
        self.update()


class BreadcrumbsManager(QWidget):
    def __init__(self, breadcrumb_widgets: List[BreadcrumbsWidget], parent=None):
        super().__init__(parent)
        # Add all breadcrumbs widget to a stack
        self.stack = QStackedWidget()
        for widget in breadcrumb_widgets:
            self.stack.addWidget(widget)
        self.link_breadcrumbs()
        # Add to the widget
        layout = QHBoxLayout(self)
        layout.addWidget(self.stack)
        self.setLayout(layout)
        # Correct height
        if breadcrumb_widgets:
            self.stack.setCurrentIndex(0)
            first_widget = breadcrumb_widgets[0]
            self.stack.setFixedHeight(first_widget.sizeHint().height() + 15)
            self.setFixedHeight(self.stack.height())

    def link_breadcrumbs(self):
        for i in range(self.stack.count()):
            breadcrumb = self.stack.widget(i)
            for j in range(self.stack.count()):
                if i == j:
                    continue
                other_breadcrumb = self.stack.widget(j)
                breadcrumb.projects_selected.connect(other_breadcrumb.back_to_root)

    def set_index(self, idx: int):
        self.stack.setCurrentIndex(idx)

    def reset(self):
        for i in range(self.stack.count()):
            self.stack.widget(i).back_to_root()

    def connect_all(self, signal_name, slot):
        # Dirty way to quickly connect the same slot and signal for all breadcrumbs
        for i in range(self.stack.count()):
            breadcrumb = self.stack.widget(i)
            if hasattr(breadcrumb, signal_name):
                getattr(breadcrumb, signal_name).connect(slot)
