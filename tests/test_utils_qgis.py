import tempfile
from pathlib import Path

import pytest
from qgis.core import QgsVectorLayer

from rana_qgis_plugin.utils.qgis import get_qml_name_for_layer, rescale_qml_ranges


def make_test_qml(min_val: float, max_val: float, num_stops: int) -> str:
    """Generate minimal test QML with rasterrenderer and colorrampshader.

    Creates color stops evenly distributed across the range [min_val, max_val].
    """
    color_stops = []
    for i in range(num_stops):
        t = i / (num_stops - 1) if num_stops > 1 else 0
        value = min_val + t * (max_val - min_val)
        label = f"{value:.4f}"
        color_stops.append(
            f'          <item alpha="255" color="#ffffff" label="{label}" value="{value}"/>'
        )

    color_stops_str = "\n".join(color_stops)

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<qgis>
  <pipe>
    <rasterrenderer type="singlebandpseudocolor" band="1" classificationMin="{min_val}" classificationMax="{max_val}" opacity="1">
      <rastershader>
        <colorrampshader type="INTERPOLATED" minimumValue="{min_val}" maximumValue="{max_val}">
{color_stops_str}
        </colorrampshader>
      </rastershader>
    </rasterrenderer>
  </pipe>
</qgis>"""


class TestRescaleQmlRanges:
    """Test QML range rescaling."""

    def test_rescale_when_needed(self):
        """Rescale from 0-1 to 0-1000."""
        qml = make_test_qml(0.0, 1.0, 5)
        rescaled = rescale_qml_ranges(qml, 0.0, 1000.0)

        assert rescaled is not None
        assert 'classificationMin="0.0"' in rescaled
        assert 'classificationMax="1000.0"' in rescaled
        assert 'minimumValue="0.0"' in rescaled
        assert 'maximumValue="1000.0"' in rescaled

        # Check that color stops are proportionally rescaled
        # Original stops at 0, 0.25, 0.5, 0.75, 1.0
        # Should rescale to 0, 250, 500, 750, 1000
        assert 'value="0.0"' in rescaled
        assert 'value="250.0"' in rescaled
        assert 'value="500.0"' in rescaled
        assert 'value="750.0"' in rescaled
        assert 'value="1000.0"' in rescaled

    def test_no_change_when_ranges_match(self):
        """Return None when ranges already match."""
        qml = make_test_qml(0.0, 1.0, 3)
        rescaled = rescale_qml_ranges(qml, 0.0, 1.0)

        assert rescaled is None


@pytest.mark.parametrize(
    "layer_name",
    [
        "simple",
        "layer_with_underscore",
        "layer-with-dash",
        "layer with spaces",
        "layer/with/slashes",
        "layer.with.dots",
        "special!@#$%^&*()",
        "layer:with:colons",
        "",
    ],
)
def test_get_qml_name_for_layer(layer_name):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir_path = Path(tmpdir)
        layer = QgsVectorLayer("Point?crs=EPSG:4326", layer_name, "memory")
        qml_path = tmpdir_path / get_qml_name_for_layer(layer_name)
        layer.saveNamedStyle(str(qml_path))
        assert qml_path.exists(), f"QML file should be created at {qml_path}"
