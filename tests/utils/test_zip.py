import io
from pathlib import Path
from zipfile import ZipFile

import pytest

from rana_qgis_plugin.utils.zip import extract_flat


def test_extract_flat_discards_directory_components(tmp_path: Path):
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("nested/style.qml", "style")

    with ZipFile(io.BytesIO(archive.getvalue())) as zip_file:
        extract_flat(zip_file, tmp_path)

    assert (tmp_path / "style.qml").read_text() == "style"
    assert not (tmp_path / "nested").exists()


def test_extract_flat_rejects_duplicate_names(tmp_path: Path):
    archive = io.BytesIO()
    with ZipFile(archive, "w") as zip_file:
        zip_file.writestr("one/style.qml", "one")
        zip_file.writestr("two/style.qml", "two")

    with ZipFile(io.BytesIO(archive.getvalue())) as zip_file:
        with pytest.raises(ValueError, match="Duplicate archive filename"):
            extract_flat(zip_file, tmp_path)
