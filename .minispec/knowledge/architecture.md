# Architecture

*Documentation for the Rana QGIS plugin architecture and component relationships.*

## High-Level Overview

The Rana QGIS plugin provides a browser interface for exploring and managing files within the Rana project. Key components:

- **RanaBrowser** — Main UI component for user interaction
- **Loader** — Manages all file download/upload operations
- **Workers** — Threaded operations for FileDownloadWorker, FileUploadWorker, VectorStyleWorker
- **Authentication** — OAuth2 for Rana, 3Di personal API key management
- **NetworkManager** — Qt-based network requests with OAuth2 token management

See README.md for detailed architecture diagram and component descriptions.

## Components & Modules

*Detailed module documentation will be added as patterns are established.*

---

## Known Architectural Challenges

### Signal Tracing
Signal chains are complex and hard to follow. Will document signal flow patterns as they're refined.

### Thread Lifecycle
Plugin reload can cause crashes due to incomplete worker cleanup. Thread lifecycle patterns will be documented.

### UI State Management
Enable/disable logic is scattered and error-prone. Cleaner state management patterns needed.

---

**Last Updated:** 2026-04-15
