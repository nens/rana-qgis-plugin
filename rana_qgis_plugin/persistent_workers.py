import time
from dataclasses import dataclass, field

from qgis.PyQt.QtCore import (
    QObject,
    QRunnable,
    QThread,
    QThreadPool,
    QTimer,
    pyqtSignal,
)

from rana_qgis_plugin.utils_api import get_project_jobs, get_project_publications


class SingleTask(QRunnable):
    """
    Wrapper around a task to run it in a separate thread.
    """

    def __init__(self, task_instance):
        super().__init__()
        self.task_instance = task_instance  # The actual worker instance

    def run(self):
        """
        Run the task instance (executes its `run` method).
        """
        self.task_instance.run()


@dataclass
class TaskData:
    worker: object
    interval: int
    last_run: float = field(default=0)

    def update_last_run(self, current_time: int):
        self.last_run = current_time

    def should_run(self, current_time: int) -> bool:
        return current_time - self.last_run >= self.interval


class PersistentTaskScheduler:
    def __init__(self):
        self.tasks = []
        self.thread_pool = QThreadPool()
        self.timer = QTimer()
        # set timer to run every second and check if any tasks need to be performed
        self.timer.timeout.connect(self._check_and_execute_tasks)
        self.global_check_interval = 1000

    def add_task(self, worker, interval):
        self.tasks.append(TaskData(worker=worker, interval=interval))

    def start(self):
        self.timer.start(self.global_check_interval)

    def stop(self):
        self.timer.stop()

    def clear(self):
        self.tasks = []

    def delete_task_by_worker(self, worker):
        for task in self.tasks:
            if task.worker == worker:
                self.tasks.remove(task)

    def run_all_tasks(self):
        self._check_and_execute_tasks(force=True)

    def _check_and_execute_tasks(self, force=False):
        current_time = time.time()
        for task in self.tasks:
            if force or task.should_run(current_time):
                runnable_task = SingleTask(task.worker)
                self.thread_pool.start(runnable_task)
                task.update_last_run(current_time)


class ProjectJobMonitorWorker(QObject):
    failed = pyqtSignal(str)
    jobs_added = pyqtSignal(list)
    job_updated = pyqtSignal(dict)

    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.active_jobs = {}
        self.project_id = project_id
        self._stop_flag = False

    def run(self):
        response = get_project_jobs(self.project_id)
        if not response:
            return
        current_jobs = response["items"]
        new_jobs = {
            job["id"]: job for job in current_jobs if job["id"] not in self.active_jobs
        }
        self.jobs_added.emit(list(new_jobs.values()))
        self.active_jobs.update(new_jobs)
        for job in current_jobs:
            if job["id"] in new_jobs:
                # new job cannot be updated
                continue
            if (
                job["state"] != self.active_jobs[job["id"]]["state"]
                or job["process"] != self.active_jobs[job["id"]]["process"]
            ):
                self.job_updated.emit(job)
                self.active_jobs[job["id"]] = job


class PublicationMonitorWorker(QObject):
    failed = pyqtSignal(str)
    publications_added = pyqtSignal(list)
    publication_updated = pyqtSignal(dict)

    def __init__(self, project_id, parent=None):
        super().__init__(parent)
        self.monitored_publications = {}
        self.project_id = project_id
        self._stop_flag = False

    def run(self):
        try:
            response = get_project_publications(self.project_id)
        except Exception as e:
            self.failed.emit(str(e))
            return
        current_publications = response["items"]
        new_publications = {
            publication["id"]: publication
            for publication in current_publications
            if publication["id"] not in self.monitored_publications
        }
        if new_publications:
            self.publications_added.emit(list(new_publications.values()))
        self.monitored_publications.update(new_publications)
        for publication in current_publications:
            if publication["id"] in new_publications:
                continue
            if (
                publication["updated_at"]
                != self.monitored_publications[publication["id"]]["updated_at"]
            ):
                self.publication_updated.emit(publication)
                self.monitored_publications[publication["id"]] = publication
