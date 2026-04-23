"""Tests for FilesBrowser default sorting behavior."""

from qgis.PyQt.QtCore import Qt

from rana_qgis_plugin.widgets.files_browser import SORT_ROLE


class TestFilesBrowserSorting:
    """Test sorting configuration of FilesBrowser."""

    def test_sort_role_constant(self):
        """Verify SORT_ROLE constant is correctly defined."""
        # SORT_ROLE should be accessible and different from standard roles
        assert SORT_ROLE is not None
        assert SORT_ROLE == Qt.ItemDataRole.UserRole + 1
