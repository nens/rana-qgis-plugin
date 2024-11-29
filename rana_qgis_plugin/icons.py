import os.path

from qgis.PyQt.QtGui import QIcon

# Base path for the icons directory
ICONS_DIR = os.path.join(os.path.dirname(__file__), "icons")

# Exported icons
login_icon = QIcon(os.path.join(ICONS_DIR, "login.svg"))
logout_icon = QIcon(os.path.join(ICONS_DIR, "logout.svg"))
refresh_icon = QIcon(os.path.join(ICONS_DIR, "refresh.svg"))
rana_icon = QIcon(os.path.join(ICONS_DIR, "rana.svg"))
