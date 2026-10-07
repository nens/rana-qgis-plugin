from unittest.mock import MagicMock, patch

from .helpers import make_loader


def test_shutdown_cancels_scenario_resolution_tasks():
    loader, _ = make_loader()
    tasks = [MagicMock(), MagicMock()]
    loader.scenario_resolve_tasks.update(tasks)

    with patch.object(loader.avatar_pool, "waitForDone"):
        loader.shutdown()

    for task in tasks:
        task.cancel.assert_called_once_with()
    assert loader.scenario_resolve_tasks == set()


def test_tracked_task_is_retained_until_completion_or_termination():
    loader, _ = make_loader()
    task = MagicMock()

    loader._track_task(task)

    assert task in loader.active_tasks
    completed = task.taskCompleted.connect.call_args.args[0]
    terminated = task.taskTerminated.connect.call_args.args[0]

    completed()
    assert task not in loader.active_tasks

    loader.active_tasks.add(task)
    terminated()
    assert task not in loader.active_tasks


def test_scenario_resolution_completion_is_ignored_after_shutdown():
    loader, _ = make_loader()
    task = MagicMock()
    continuation = MagicMock()
    request = MagicMock()
    scenario_info = MagicMock()
    loader.scenario_resolve_tasks.add(task)

    with patch.object(loader.avatar_pool, "waitForDone"):
        loader.shutdown()
    assert loader._accept_async_callbacks is False
    loader.finish_scenario_resolution(task, continuation, request, scenario_info)

    continuation.assert_not_called()
