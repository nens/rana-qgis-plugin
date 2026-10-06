# Glossary

*Domain terms and technical terminology used in the Rana QGIS plugin.*

## Rana Ecosystem

- **Rana** — The backend system for project management and file hosting
- **RDC** — Rana Desktop Client; the QGIS-based desktop interface
- **Rana API** — RESTful API for backend communication

## 3Di Integration

- **3Di** — Hydrological modeling and simulation platform
- **3Di API** — API for 3Di models and simulations
- **3Di Personal API Key** — Per-user authentication token, auto-generated via Rana API

## Plugin Components

- **RanaBrowser** — Main UI component for file browsing and management
- **Loader** — Core logic for file download/upload operations
- **Worker** — QThread-based background task executor (FileDownloadWorker, FileUploadWorker, VectorStyleWorker)
- **NetworkManager** — Qt Network-based request handler with OAuth2 integration

## Authentication

- **OAuth2** — Authentication protocol used for Rana API access
- **Token Refresh** — Automatic renewal of expired OAuth2 tokens
- **Personal Access Token (PAK)** — Long-lived token for programmatic access

## QGIS/Qt Terms

- **Signal** — Qt mechanism for loose coupling between components
- **Slot** — Qt handler for a signal
- **QThread** — Qt's threading abstraction
- **QML** — QGIS Vector Style file format (XML-based styling)

---

*Terms will be added as new domain concepts emerge during development.*

**Last Updated:** 2026-04-15
