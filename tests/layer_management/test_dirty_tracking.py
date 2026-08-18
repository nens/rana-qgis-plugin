from qgis.core import QgsVectorLayer

from rana_qgis_plugin.layer_management.dirty_tracking import (
    DATA_DIRTY_PROPERTY,
    STYLE_DIRTY_PROPERTY,
    attach_dirty_tracking,
    is_data_dirty,
    is_style_dirty,
)


def test_vector_commit_marks_data_dirty(qgis_application):
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")
    attach_dirty_tracking(layer)

    assert not is_data_dirty(layer)
    layer.startEditing()
    layer.commitChanges()

    assert is_data_dirty(layer)
    assert layer.customProperty(DATA_DIRTY_PROPERTY) is True


def test_style_change_marks_style_dirty(qgis_application):
    layer = QgsVectorLayer("Point?crs=EPSG:4326", "test", "memory")
    attach_dirty_tracking(layer)

    assert not is_style_dirty(layer)
    layer.styleChanged.emit()

    assert is_style_dirty(layer)
    assert layer.customProperty(STYLE_DIRTY_PROPERTY) is True
