# Layer Manager Documentation

## Overview

The layer manager system handles loading files and schematisations into QGIS as layers. It abstracts away the complexity of creating different layer types (raster, vector, WMS, scenario results) and organizing them in the layer tree.

The architecture uses the **Strategy Pattern** with a base class (`LayerManager`) and specialized subclasses for different loading contexts:
- **FileLayerManager**: Loads files from the project file browser
- **PublicationLayerManager**: Loads layers from published versions with specific layer filtering

This separation allows each context to customize layer organization, naming, and validation without duplicating layer creation logic.

## Core Concepts

### Layer Types

The layer manager handles four main file types:

| Type | Method | Behavior |
|------|--------|----------|
| **Raster** | `_add_layer_from_raster_file()` | Creates single QgsRasterLayer from `.tif` or similar. Applies custom style if `.qml` exists in same directory. |
| **Vector** | `_add_layers_from_vector_file()` | Extracts individual layers from multi-layer file (GeoPackage, Shapefile). Creates separate QgsVectorLayer for each. Applies custom style per layer. |
| **Scenario** | `_add_layer_from_scenario()` | For 3Di simulation results. Loads into Results Analysis tool if available. Adds water depth raster with predefined styling. |
| **Schematisation** | `add_from_schematisation()` | Downloads remote 3Di schematisation. Requires working directory. Integrates with 3Di simulation environment. |

### Layer Organization

Layers are organized in QGIS layer tree using **parent groups**. Each layer manager can specify a hierarchy:

**FileLayerManager**:
```
Project Name
├── folder
│   └── subfolder
│       └── Layer Name
```

**PublicationLayerManager**:
```
Project Name
└── publications
    └── publication
        └── version
            └── layer name
```

### Vector File Handling

Vector files (GeoPackage) can contain multiple layers. The system handles this intelligently:

1. **FileLayerManager**: Loads **all layers** from the file
   - Uses `_add_all_layers_from_vector_file()`
   - Each layer gets its own node in the layer tree
   - Style applied per layer if available

2. **PublicationLayerManager**: Loads **specific layer only**
   - Constructor parameter `layer_in_file` specifies which layer
   - Only that layer is added to the map
   - Custom `display_name` used for layer naming


## Layer Deduplication

The layer manager prevents duplicate layers by checking if a layer with the same name and source already exists based on name and source. If a duplicate is found, it is removed and replaced with the new layer.


## FileLayerManager

Used when opening files from the project file browser.

**Characteristics**:
- Loads all layers from a file
- Organizes by project directory structure
- Saves last modified date for conflict detection

## PublicationLayerManager

Used when opening layers from published versions. More specialized than FileLayerManager.

**Characteristics**:
- Filters to specific layer within a file (via `layer_in_file` parameter)
- Uses custom display names (from publication metadata)
- Organizes under "publications" parent group
- Each publication layer is treated as an independent layer
