"""Interactively remove leftover projects from the e2e tenant."""

import argparse
import os
import sys
from collections.abc import Callable, Sequence

from qgis.core import QgsApplication, QgsAuthMethodConfig
from qgis.PyQt.QtCore import QSettings

from rana_qgis_plugin.constant import RANA_AUTHCFG_ENTRY, RANA_SETTINGS_ENTRY
from rana_qgis_plugin.utils.api import delete_project, get_tenant_projects
from rana_qgis_plugin.utils.settings import set_base_url, set_tenant_id

E2E_TENANT_ID = "rdc-e2e"
E2E_BASE_URL = "https://test.ranawaterintelligence.com"


def configure_auth() -> None:
    """Configure the Rana auth entry in the same way as the e2e fixture."""
    secret = os.getenv("RANA_PAK")
    if not secret:
        raise RuntimeError("RANA_PAK is not set")

    auth_manager = QgsApplication.authManager()
    if not auth_manager.authenticationDatabasePath():
        auth_manager.setup()
    if not auth_manager.masterPasswordIsSet():
        auth_manager.setMasterPassword("test", True)

    authcfg = QgsAuthMethodConfig()
    authcfg.setName(RANA_SETTINGS_ENTRY)
    authcfg.setMethod("Basic")
    authcfg.setConfig("username", "__key__")
    authcfg.setConfig("password", secret)
    if not authcfg.isValid():
        raise RuntimeError("Could not create the Rana authentication configuration")
    if not auth_manager.storeAuthenticationConfig(authcfg):
        raise RuntimeError("Could not store the Rana authentication configuration")
    if not authcfg.id():
        raise RuntimeError("The Rana authentication configuration has no ID")

    QSettings().setValue(RANA_AUTHCFG_ENTRY, authcfg.id())
    set_base_url(E2E_BASE_URL)
    set_tenant_id(E2E_TENANT_ID)


def get_e2e_projects() -> list[dict]:
    """Return only projects belonging to the e2e naming convention."""
    projects = get_tenant_projects()["items"]
    return [project for project in projects if project.get("name", "")]


def format_project(project: dict) -> str:
    return f"{project.get('name', '<unnamed>')} ({project.get('id', '<no id>')})"


def confirm_deletion(
    projects: Sequence[dict], input_func: Callable[[str], str] = input
) -> bool:
    print(f"\nFound {len(projects)} project(s) in tenant {E2E_TENANT_ID}:")
    for project in projects:
        print(f"  - {format_project(project)}")
    answer = input_func("\nDelete these projects? [y/N]: ")
    return answer.strip().lower() == "y"


def delete_projects(projects: Sequence[dict]) -> int:
    failures = 0
    for project in projects:
        project_id = project.get("id")
        if not project_id:
            print(f"FAILED {format_project(project)}: missing project ID")
            failures += 1
            continue
        if delete_project(project_id):
            print(f"Deleted {format_project(project)}")
        else:
            print(f"FAILED to delete {format_project(project)}")
            failures += 1
    return failures


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--list", action="store_true", help="list projects without asking to delete"
    )
    args = parser.parse_args(argv)

    QgsApplication.setPrefixPath("/usr", True)
    qgs = QgsApplication([], False)
    qgs.initQgis()
    try:
        configure_auth()
        projects = get_e2e_projects()
        if not projects:
            print(f"No projects found in tenant {E2E_TENANT_ID}.")
            return 0
        if args.list:
            for project in projects:
                print(format_project(project))
            return 0
        if not confirm_deletion(projects):
            print("No projects deleted.")
            return 0
        return 1 if delete_projects(projects) else 0
    finally:
        qgs.exitQgis()


if __name__ == "__main__":
    sys.exit(main())
