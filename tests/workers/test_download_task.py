import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock

from rana_qgis_plugin.workers.download import DownloadTask, RanaFileDownloader


def test_download_task_downloads_jobs_sequentially():
    pass
    first = MagicMock(file_id="first")
    second = MagicMock(file_id="second")
    task = DownloadTask([first, second])

    assert task.run()
    first.download_file.assert_called_once()
    second.download_file.assert_called_once()
    assert task.successful_files == ["first", "second"]


def test_download_task_reports_failed_file():
    pass
    downloader = MagicMock(file_id="broken")

    def fail(signals):
        signals.failed.emit("download failed")

    downloader.download_file.side_effect = fail
    task = DownloadTask([downloader])

    assert not task.run()
    assert task.failed_files == [("broken", "download failed")]


def test_download_task_normalizes_integer_file_id_for_signals():
    downloader = MagicMock(file_id=123)
    started_files = []
    task = DownloadTask([downloader])
    task.file_started.connect(started_files.append)

    assert task.run()

    assert started_files == ["123"]
    assert task.successful_files == ["123"]
