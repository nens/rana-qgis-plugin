from unittest.mock import patch

from qgis.core import QgsTask

from rana_qgis_plugin.workers.rana_jobs import JobLogsFetchTask, JobsFetchTask


def test_jobs_fetch_task_stores_result():
    result = {"items": [{"id": "job-1"}]}
    task = JobsFetchTask("project-1", {"search": "model"})

    with patch(
        "rana_qgis_plugin.workers.rana_jobs.get_project_jobs", return_value=result
    ) as fetch:
        assert task.run()

    fetch.assert_called_once_with("project-1", params={"search": "model"})
    assert task.result is result
    assert task.error is None


def test_jobs_fetch_task_stores_error():
    error = RuntimeError("fetch failed")
    task = JobsFetchTask("project-1")

    with patch(
        "rana_qgis_plugin.workers.rana_jobs.get_project_jobs", side_effect=error
    ) as fetch:
        assert not task.run()

    fetch.assert_called_once_with("project-1", params={})
    assert task.result is None
    assert task.error is error


def test_jobs_fetch_task_copies_filter_params():
    params = {"search": "model"}
    task = JobsFetchTask("project-1", params)
    params["search"] = "changed"

    with patch(
        "rana_qgis_plugin.workers.rana_jobs.get_project_jobs",
        return_value={"items": []},
    ) as fetch:
        assert task.run()

    fetch.assert_called_once_with("project-1", params={"search": "model"})


def test_jobs_fetch_task_is_hidden_and_not_cancellable():
    task = JobsFetchTask("project-1")

    assert int(task.flags() & QgsTask.Flag.Hidden) != 0
    assert int(task.flags() & QgsTask.Flag.CanCancel) == 0
    assert int(task.flags() & QgsTask.Flag.Silent) != 0


def test_job_logs_fetch_task_stores_result():
    result = {"items": [{"message": "hello"}]}
    task = JobLogsFetchTask("job-1")

    with patch(
        "rana_qgis_plugin.workers.rana_jobs.get_job_logs", return_value=result
    ) as fetch:
        assert task.run()

    fetch.assert_called_once_with("job-1")
    assert task.job_id == "job-1"
    assert task.result is result
    assert task.error is None


def test_job_logs_fetch_task_stores_error():
    error = RuntimeError("logs failed")
    task = JobLogsFetchTask("job-1")

    with patch("rana_qgis_plugin.workers.rana_jobs.get_job_logs", side_effect=error):
        assert not task.run()

    assert task.result is None
    assert task.error is error


def test_job_logs_fetch_task_is_hidden_and_not_cancellable():
    task = JobLogsFetchTask("job-1")

    assert int(task.flags() & QgsTask.Flag.Hidden) != 0
    assert int(task.flags() & QgsTask.Flag.CanCancel) == 0


def test_cancelled_jobs_fetch_task_skips_request():
    task = JobsFetchTask("project-1")

    with (
        patch.object(task, "isCanceled", return_value=True),
        patch("rana_qgis_plugin.workers.rana_jobs.get_project_jobs") as fetch,
    ):
        assert not task.run()

    fetch.assert_not_called()
