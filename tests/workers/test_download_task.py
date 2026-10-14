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


def _style_zip(**members: str) -> bytes:
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, "w") as zip_file:
        for name, content in members.items():
            zip_file.writestr(name, content)
    return archive.getvalue()


QML_WITH_RANA_PROPERTIES = """<!DOCTYPE qgis>
<qgis version="3.40.0">
  <customproperties>
    <Option type="Map">
      <Option name="rana/style_dirty" type="bool" value="true"/>
      <Option name="rana/project_id" type="QString" value="stale-project"/>
      <Option name="variableNames" type="QString" value="keep-me"/>
    </Option>
  </customproperties>
</qgis>
"""


def _downloader_for(tmp_path: Path, data_type: str, file_name: str, zip_bytes: bytes):
    context = MagicMock()
    context.local_dir = tmp_path
    context.local_file_path = tmp_path / file_name
    context.get_style_zip.return_value = zip_bytes
    return RanaFileDownloader(
        {"id": "project"},
        {"id": file_name, "data_type": data_type, "descriptor_id": "descriptor"},
        context,
    )


def test_postprocess_strips_rana_properties_from_downloaded_vector_style(
    tmp_path: Path,
):
    downloader = _downloader_for(
        tmp_path,
        "vector",
        "roads.gpkg",
        _style_zip(**{"points.qml": QML_WITH_RANA_PROPERTIES}),
    )

    downloader.postprocess()

    text = (tmp_path / "points.qml").read_text()
    assert "rana/" not in text
    assert "keep-me" in text


def test_postprocess_strips_rana_properties_from_downloaded_raster_style(
    tmp_path: Path,
):
    """The raster style is renamed to the sidecar name QGIS auto-loads, so it
    must be clean on disk before any layer is ever constructed from it."""
    downloader = _downloader_for(
        tmp_path,
        "raster",
        "dem.tif",
        _style_zip(**{"physical_quantity.qml": QML_WITH_RANA_PROPERTIES}),
    )
    downloader._rescale_qml_to_raster_range = lambda qml_path: None

    downloader.postprocess()

    sidecar = tmp_path / "dem.qml"
    assert sidecar.exists(), "physical_quantity.qml should be renamed to <stem>.qml"
    text = sidecar.read_text()
    assert "rana/" not in text
    assert "keep-me" in text


def test_postprocess_leaves_unrelated_sibling_styles_alone(tmp_path: Path):
    """Cached files from one Rana folder share a directory, so the strip must
    touch only what this download extracted."""
    sibling = tmp_path / "other.qml"
    sibling.write_text(QML_WITH_RANA_PROPERTIES)
    downloader = _downloader_for(
        tmp_path,
        "vector",
        "roads.gpkg",
        _style_zip(**{"points.qml": QML_WITH_RANA_PROPERTIES}),
    )

    downloader.postprocess()

    assert "rana/" not in (tmp_path / "points.qml").read_text()
    assert sibling.read_text() == QML_WITH_RANA_PROPERTIES
