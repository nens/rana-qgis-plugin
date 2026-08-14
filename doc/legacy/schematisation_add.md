# Adding a schematisation

**Version: 1.2.15+**

## Overview

This document describes the API interactions when creating a schematisation in the RANA QGIS plugin. Two entry points are supported:

- **New schematisation** — user defines schema and data via a 3-page wizard
- **Existing schematisation** — user provides an existing GeoPackage/SQLite file

Both flows result in the same sequence of API calls to HCC and Rana.

## Simplified flow diagram

```mermaid
flowchart TD
    subgraph "HCC (3Di API)"
        HCC1["POST /schematisations/"]
        HCC3["POST /revisions/"]
        HCC4["PUT files to S3"]
        HCC5["POST /commit/"]
    end
    subgraph "Rana"
        Rana1["POST /threedi-schematisations/<br/>(register schematisation)"]
        Rana2["Start model_tracker process"]
    end
    
    HCC1 --> Rana1
    Rana1 --> HCC3
    HCC3 --> HCC4
    HCC4 --> HCC5
    HCC5 --> Rana2
```


## Key changes

### v1.2.15+

**From v1.2.15 onwards:** Rana registration happens **last**, after the revision is fully committed to HCC and model creation is requested. This ensures the schematisation is validated and complete on HCC before Rana registration.

```mermaid
flowchart TD
    subgraph "HCC (3Di API)"
        HCC1["POST /schematisations/"]
        HCC2["POST /revisions/"]
        HCC3["PUT files to S3"]
        HCC4["POST /commit/"]
    end
    subgraph "Rana"
        Rana1["Start model_tracker process"]
        Rana2["POST /threedi-schematisations/<br/>(register schematisation)"]
    end
    
    HCC1 --> HCC2
    HCC2 --> HCC3
    HCC3 --> HCC4
    HCC4 --> Rana1
    Rana1 --> Rana2
```
