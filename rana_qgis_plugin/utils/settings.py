import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from qgis.core import Qgis, QgsApplication, QgsMessageLog, QgsSettings

from rana_qgis_plugin.constant import (
    COGNITO_LOGOUT_ENDPOINT,
    RANA_API_VERSION_PREFIX,
    RANA_CLENUP_CACHE_ON_CLOSE_ENTRY,
    RANA_SETTINGS_ENTRY,
    RANA_TENANT_ENTRY,
)


def logout_redirect_uri() -> str:
    return f"{base_url()}/auth/callback/cognito/logout"


def logout_redirect_uri_encoded() -> str:
    return quote(logout_redirect_uri(), safe="")


def logout_url() -> str:
    return f"{COGNITO_LOGOUT_ENDPOINT}?client_id={cognito_client_id()}&logout_uri={logout_redirect_uri_encoded()}"


def hcc_working_dir() -> str:
    # Backwards compatible to older software
    return QgsSettings().value("threedi/working_dir")


def set_hcc_working_dir(working_dir: str) -> None:
    # Backwards compatible to older software
    QgsSettings().setValue("threedi/working_dir", working_dir)
    os.makedirs(hcc_working_dir(), exist_ok=True)


def rana_cache_dir() -> str:
    default = str(Path.home() / "Rana")
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cache_dir", default)


def set_rana_cache_dir(cache_dir: str) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cache_dir", cache_dir)


def cleanup_cache_on_close() -> bool:
    return QgsSettings().value(RANA_CLENUP_CACHE_ON_CLOSE_ENTRY, False, type=bool)


def set_cleanup_cache_on_close(value: bool) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cleanup_cache_on_close", value)


def get_use_plugin_excepthook() -> bool:
    return QgsSettings().value(
        f"{RANA_SETTINGS_ENTRY}/use_plugin_excepthook", True, type=bool
    )


def get_hcc_url_override() -> Optional[str]:
    value = QgsSettings().value("Rana/hcc_url")
    return value if value else None


def get_advanced_settings() -> dict:
    advanced_settings = {}
    settings_names = ["use_plugin_excepthook", "hcc_url", "rana_api_version_prefix"]
    for setting_name in settings_names:
        value = QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/{setting_name}")
        if value is not None:
            advanced_settings[setting_name] = value
    return advanced_settings


def hidden_projects_file() -> Path:
    return Path(QgsApplication.qgisSettingsDirPath()) / "rana" / "hidden_projects.json"


def read_hidden_projects() -> dict[str, list[str]]:
    """Read the hidden-project store, returning an empty store if invalid."""
    path = hidden_projects_file()
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as file:
            data = json.load(file)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        QgsMessageLog.logMessage(
            f"Could not read hidden projects from {path}: {error}",
            "Rana",
            Qgis.MessageLevel.Warning,
        )
        return {}

    if not isinstance(data, dict):
        QgsMessageLog.logMessage(
            f"Ignoring invalid hidden projects data in {path}",
            "Rana",
            Qgis.MessageLevel.Warning,
        )
        return {}

    return {
        key: project_ids
        for key, project_ids in data.items()
        if isinstance(key, str)
        and isinstance(project_ids, list)
        and all(isinstance(project_id, str) for project_id in project_ids)
    }


def get_hidden_projects(base_url: str, tenant_id: str) -> set[str]:
    """Return the set of hidden project IDs for the given backend and tenant."""
    data = read_hidden_projects()
    print(f"{data=}")
    return set(data.get(f"{base_url.rstrip('/')}|{tenant_id}", []))


def set_hidden_projects(base_url: str, tenant_id: str, hidden_ids: set) -> None:
    """Overwrite the hidden project IDs for the given backend and tenant."""
    path = hidden_projects_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = read_hidden_projects()
    key = f"{base_url.rstrip('/')}|{tenant_id}"
    if hidden_ids:
        data[key] = sorted(hidden_ids)
    else:
        data.pop(key, None)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(data, f)
    tmp.replace(path)


def hide_project(base_url: str, tenant_id: str, project_id: str) -> None:
    """Add a single project to the hidden set."""
    hidden = get_hidden_projects(base_url, tenant_id)
    hidden.add(project_id)
    set_hidden_projects(base_url, tenant_id, hidden)


def unhide_project(base_url: str, tenant_id: str, project_id: str) -> None:
    """Remove a single project from the hidden set."""
    hidden = get_hidden_projects(base_url, tenant_id)
    hidden.discard(project_id)
    set_hidden_projects(base_url, tenant_id, hidden)


def initialize_settings() -> None:
    """Sets up the settings with default values"""
    settings = QgsSettings()

    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/cognito_client_id",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/cognito_client_id", "250mkcukj5tn6lblsd6ka42c0a"
        ),
    )
    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native",
            "2epleb6bkli509b0a6fmddcrj6",
        ),
    )
    settings.setValue(
        f"{RANA_SETTINGS_ENTRY}/base_url",
        settings.value(
            f"{RANA_SETTINGS_ENTRY}/base_url", "https://www.ranawaterintelligence.com"
        ),
    )

    documents_folder = os.path.join(os.path.expanduser("~"), "Documents", "Rana")
    settings.setValue(
        "threedi/working_dir",
        settings.value("threedi/working_dir", Path(documents_folder).as_posix()),
    )
    os.makedirs(settings.value("threedi/working_dir"), exist_ok=True)


def set_tenant_id(tenant: str) -> None:
    QgsSettings().setValue(RANA_TENANT_ENTRY, tenant)


def get_tenant_id() -> str:
    return QgsSettings().value(RANA_TENANT_ENTRY)


def set_cognito_client_id(id: str) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cognito_client_id", id)


def cognito_client_id() -> str:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cognito_client_id")


def set_cognito_client_id_native(id: str) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native", id)


def cognito_client_id_native() -> str:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/cognito_client_id_native")


def set_base_url(url: str) -> None:
    QgsSettings().setValue(f"{RANA_SETTINGS_ENTRY}/base_url", url.rstrip("/"))


def base_url() -> str:
    return QgsSettings().value(f"{RANA_SETTINGS_ENTRY}/base_url")


def api_version_prefix() -> str:
    return QgsSettings().value(
        f"{RANA_SETTINGS_ENTRY}/rana_api_version_prefix", RANA_API_VERSION_PREFIX
    )


def api_url() -> str:
    return f"{base_url()}/{api_version_prefix()}"
