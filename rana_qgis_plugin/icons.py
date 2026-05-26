import os.path

from qgis.core import QgsApplication
from qgis.PyQt.QtGui import QIcon
from qgis.PyQt.QtWidgets import QApplication, QStyle

# Base path for the icons directory
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

# Exported custom icons
login_icon = QIcon(os.path.join(ICONS_DIR, "login.svg"))
logout_icon = QIcon(os.path.join(ICONS_DIR, "logout.svg"))
refresh_icon = QIcon(os.path.join(ICONS_DIR, "refresh.svg"))
rana_icon = QIcon(os.path.join(ICONS_DIR, "rana.svg"))
separator_icon = QIcon(os.path.join(ICONS_DIR, "separator.svg"))
ellipsis_icon = QIcon(os.path.join(ICONS_DIR, "ellipsis.svg"))
settings_icon = QgsApplication.getThemeIcon("/processingAlgorithm.svg")
add_icon = QIcon(os.path.join(ICONS_DIR, "add.svg"))

copy_icon = QIcon(os.path.join(ICONS_DIR, "copy.svg"))
download_icon = QIcon(os.path.join(ICONS_DIR, "download.svg"))
edit_icon = QIcon(os.path.join(ICONS_DIR, "edit.svg"))
dir_icon = QIcon(os.path.join(ICONS_DIR, "folder.svg"))
history_icon = QIcon(os.path.join(ICONS_DIR, "history.svg"))
link_icon = QIcon(os.path.join(ICONS_DIR, "link.svg"))
style_icon = QIcon(os.path.join(ICONS_DIR, "style.svg"))
trash_icon = QIcon(os.path.join(ICONS_DIR, "trash.svg"))
upload_icon = QIcon(os.path.join(ICONS_DIR, "upload.svg"))
wms_icon = QIcon(os.path.join(ICONS_DIR, "wms.svg"))
