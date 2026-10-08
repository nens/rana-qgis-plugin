# Glossary

*Domain terms and technical terminology used in the Rana QGIS data provider.*

## Rana Ecosystem

- **Rana** — The backend system for project management and file hosting
- **RDC** — Rana Desktop Client; the QGIS-based desktop interface
- **Rana API** — RESTful API for backend communication
- **Tenant** — Organizational unit in Rana; user selects tenant at login

## 3Di Integration

- **3Di** — Hydrological modeling and simulation platform
- **3Di API** — API for 3Di models and simulations
- **3Di Personal API Key** — Per-user authentication token, auto-generated via Rana API

## Plugin Components (Rewrite)

- **QgsDataItemProvider** — QGIS interface for registering custom data sources in the Browser panel
- **Root Item** — Always-visible "Rana" node in Browser; entry point for all interactions
- **Data Item** — A node in the QGIS Browser tree representing a Rana resource

## Authentication

- **OAuth2** — Authentication protocol used for Rana API access (via AWS Cognito)
- **Token Refresh** — Automatic renewal of expired OAuth2 tokens
- **Personal Access Token (PAK)** — Long-lived token for programmatic access

## Legacy Components (Reference)

- **RanaBrowser** — Former main UI component (dock widget)
- **Loader** — Former core logic for file download/upload operations
- **Worker** — Former QThread-based background task executor
- **NetworkManager** — Former Qt Network-based request handler with OAuth2 integration

## QGIS/Qt Terms

- **Signal** — Qt mechanism for loose coupling between components
- **Slot** — Qt handler for a signal
- **QThread** — Qt's threading abstraction
- **QML** — QGIS Vector Style file format (XML-based styling)

---

*Terms will be added as new domain concepts emerge during development.*

**Last Updated:** 2026-07-31
