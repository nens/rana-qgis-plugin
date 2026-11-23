from typing import cast

from qgis.core import QgsTask

from rana_qgis_plugin.utils.api import get_job_logs, get_project_jobs


def hidden_task_flags() -> QgsTask.Flags:
    """Flags for internal fetches: hidden from the task manager and not cancellable."""
    return cast(QgsTask.Flags, QgsTask.Flag.Hidden | QgsTask.Flag.Silent)


class JobsFetchTask(QgsTask):
    """Fetch project jobs without blocking the QGIS GUI thread."""

    def __init__(self, project_id: str, params: dict | None = None):
        super().__init__("Fetch project jobs", flags=hidden_task_flags())
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


class JobLogsFetchTask(QgsTask):
    """Fetch the logs of one job without blocking the QGIS GUI thread."""

    def __init__(self, job_id: str):
        super().__init__("Fetch job logs", flags=hidden_task_flags())
        self.job_id = job_id
        self.result: dict | None = None
        self.error: Exception | None = None

    def run(self) -> bool:
        """Run the job log fetch on the task worker thread."""
        if self.isCanceled():
            return False
        try:
            self.result = get_job_logs(self.job_id)
        except Exception as error:
            self.error = error
            return False
        return not self.isCanceled()
