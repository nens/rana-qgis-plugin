import unittest

from qgis.PyQt.QtCore import QTimer


def test_download_project(plugin, qgis_application):
    """Test failing request"""
    QTimer.singleShot(0, plugin.run)
    assert False
