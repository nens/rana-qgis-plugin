from qgis.core import QgsTask

from rana_qgis_plugin.workers.history import ModelDeleteResult, ModelDeleteTask


def test_delete_task_stores_result():
    task = ModelDeleteTask(lambda: ModelDeleteResult(is_generating=True))

    assert task.run() is True
    assert task.result == ModelDeleteResult(is_generating=True)


def test_delete_task_reports_unexpected_exception_as_error():
    def fail():
        raise ConnectionError("connection reset")

    task = ModelDeleteTask(fail)

    assert task.run() is True
    assert task.result.error == "connection reset"


def test_delete_task_is_not_cancelable():
    task = ModelDeleteTask(lambda: ModelDeleteResult())

    assert not task.flags() & QgsTask.Flag.CanCancel
