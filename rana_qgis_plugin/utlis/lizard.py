#!/usr/bin/env python3
"""
Import colormaps from GeoStyler format.

Copied from N&S colormaps library
"""


def hex_to_rgba(hex_color, opacity=1.0):
    """
    Convert hex color string to RGBA array.

    Args:
        hex_color: Hex color string (e.g., "#6b0a5c")
        opacity: Opacity value between 0.0 and 1.0

    Returns:
        RGBA array with values 0-255

    Raises:
        ValueError: If hex_color is invalid format
    """
    if not hex_color.startswith("#") or len(hex_color) != 7:
        raise ValueError(f"Invalid hex color format: {hex_color}")

    try:
        # Remove # and convert to RGB
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        a = int(opacity * 255)

        return [r, g, b, a]
    except ValueError as e:
        raise ValueError(f"Invalid hex color format: {hex_color}") from e


def _extract_colormap_entries(raster_symbolizer):
    """
    Extract colormap entries and type from GeoStyler structure.

    Args:
        raster_symbolizer: GeoStyler Raster  Symbolizer dict

    Returns:
        Tuple of (colormap entry dictionaries, colormap type)

    Raises:
        KeyError: If required structure is missing
    """
    try:
        if raster_symbolizer["kind"] != "Raster":
            raise ValueError("Expected Raster symbolizer")
        color_map = raster_symbolizer["colorMap"]
        return color_map["colorMapEntries"], color_map["type"]

    except (KeyError, IndexError, TypeError):
        raise KeyError("Invalid GeoStyler structure: missing required fields")


def import_from_geostyler(raster_symbolizer):
    """
    Import colormap from a Geostyler raster symbolizaer

    For "intervals" type, creates discrete bands by duplicating entries
    at transitionpoints.
    For "values" type, creates discrete colormap with each entry as-is.
    For "ramp" type, creates smooth gradients with single entries.

    Args:
        raster_symbolizer: GeoStyler Raster Symbolizer dict

    Returns:
        dict that can be loaded into colormap
    """
    entries, colormap_type = _extract_colormap_entries(raster_symbolizer)

    if not entries:
        raise ValueError("No colormap entries found")

    # Sort entries by quantity to ensure proper ordering
    entries = sorted(entries, key=lambda x: x["quantity"])

    # Transform all entries to colormap format
    data = [_transform_color_entry(entry) for entry in entries]

    # Extract labels if present
    labels = _extract_labels(entries)

    if colormap_type == "intervals":
        result = {
            "type": "GradientColormap",
            "data": _create_interval_data(data),
            "free": False,
        }
    elif colormap_type == "values":
        result = {"type": "DiscreteColormap", "data": data}
    elif colormap_type == "ramp":
        result = {"type": "GradientColormap", "data": data, "free": False}
    else:
        raise ValueError(f"Unsupported colormap type: {colormap_type}")

    # Add labels if any were found
    if labels:
        result["labels"] = labels

    return result


def _extract_labels(entries):
    """
    Extract labels from colormap entries.

    Args:
        entries: List of colormap entries that may contain 'label' field

    Returns:
        Dictionary with 'nl_NL' key containing list of [quantity, label] pairs,
        or empty dict if no labels found
    """
    labeled_entries = []
    for entry in entries:
        if "label" in entry and entry["label"]:
            labeled_entries.append([entry["quantity"], entry["label"]])

    if labeled_entries:
        return {"nl_NL": labeled_entries}
    return {}


def _transform_color_entry(entry):
    return [entry["quantity"], hex_to_rgba(entry["color"], entry.get("opacity", 1.0))]


def _create_interval_data(data):
    """
    Create data for discrete interval colormap.

    An entry means that everything <= that value should get that color.

    Args:
        data: List of [quantity, rgba] pairs already transformed
    """
    result = []

    for i, transformed_entry in enumerate(data):
        value, rgba = transformed_entry

        # Add a duplicate of the previous entry's value (unless it's the first)
        if i > 0:
            previous_value = data[i - 1][0]
            result.append([previous_value, rgba])

        # Add the entry at its position (unless it's the last entry)
        if i < len(data) - 1:
            result.append([value, rgba])

    return result
