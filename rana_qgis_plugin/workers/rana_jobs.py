from typing import cast

from qgis.core import QgsTask

from rana_qgis_plugin.utils.api import get_project_jobs


class JobsFetchTask(QgsTask):
    """Fetch project jobs without blocking the QGIS GUI thread."""

    def __init__(self, project_id: str, params: dict | None = None):
        flags = cast(
            QgsTask.Flags,
            QgsTask.Flag.CanCancel
            | QgsTask.Flag.CancelWithoutPrompt
            | QgsTask.Flag.Silent,
        )
        super().__init__("Fetch project jobs", flags=flags)
        self.project_id = project_id
        self.params = params.copy() if params else {}
        self.result: dict | None = None
        self.error: Exception | None = None

    def run(self) -> bool:
        """Run the job fetch on the task worker thread."""
        if self.isCanceled():
            return False
        try:
            self.result = get_project_jobs(self.project_id, params=self.params)
        except Exception as error:
            self.error = error
            return False
        return not self.isCanceled()
