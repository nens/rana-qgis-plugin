from unittest.mock import MagicMock

import pytest

from rana_qgis_plugin.widgets.file_info_models import (
    FieldValue,
    FileInfoModel,
    GeneralInfo,
    InfoSection,
    ScenarioFileInfoModel,
    SchematisationFileInfoModel,
    get_file_info_model_class,
)


def test_field_value_from_dict_valid():
    fv = FieldValue.from_dict({"foo": "bar"}, "foo")
    assert fv.error is False
    assert fv.value == "bar"


@pytest.mark.parametrize(
    "dict_data,key",
    [
        ({"foo": "bar"}, "missing"),
        (None, "foo"),
        ({}, "foo"),
    ],
)
def test_field_value_from_dict_with_error(dict_data, key):
    fv = FieldValue.from_dict(dict_data, key, default="fallback")
    assert fv.error == True
    assert fv.value == "fallback"


def test_missing_field_is_explicitly_marked():
    field = FieldValue.from_dict({}, "name")

    assert field.error is True
    assert field.value is None


@pytest.mark.parametrize(
    "data_type,model_cls",
    [
        ("scenario", ScenarioFileInfoModel),
        ("threedi_schematisation", SchematisationFileInfoModel),
        ("other", FileInfoModel),
    ],
)
def test_get_file_info_model_class(data_type: str, model_cls):
    assert get_file_info_model_class(data_type) == model_cls


@pytest.mark.parametrize("descriptor", [None, {}])
@pytest.mark.parametrize("file_data", [None, {}])
def test_file_info_model_safe_with_missing_data(descriptor, file_data):
    # ensure that model doesn't fail with missing data
    model = FileInfoModel(descriptor=descriptor, file_data=file_data)
    general_info = model.get_general_info()
    assert isinstance(general_info, GeneralInfo)
    more_info = model.get_more_section()
    assert isinstance(more_info, InfoSection)
    assert model.get_related_files() == []


def test_schematisation_file_mode_safe_with_missing_data():
    model = SchematisationFileInfoModel(
        descriptor=None,
        file_data=None,
        schematisation_data=None,
        threedi_model_data=None,
    )
    general_info = model.get_general_info()
    assert isinstance(general_info, GeneralInfo)
    more_info = model.get_more_section()
    assert isinstance(more_info, InfoSection)
    assert model.get_related_files() == []


@pytest.mark.parametrize("data_type", ["scenario", "threedi_schematisation"])
def test_file_info_model_more_section_rows(data_type):
    expected_row_names = ["Projection", "Type", "Status"]
    if data_type != "threedi_schematisation":
        expected_row_names.append("Storage")
    model = FileInfoModel(descriptor=None, file_data={"data_type": data_type})
    more_info_row_names = [row.key for row in model.get_more_section().rows]
    assert more_info_row_names == expected_row_names


def test_scenario_file_info_model_more_section_rows():
    model = ScenarioFileInfoModel(descriptor=None, file_data=None)
    more_info_row_names = [row.key for row in model.get_more_section().rows]
    expected_row_names = [
        "Projection",
        "Type",
        "Status",
        "Storage",
        "Simulation name",
        "Simulation ID",
        "Schematisation name",
        "Schematisation ID",
        "Schematisation version",
        "Revision ID",
        "Model ID",
        "Model software",
        "Software version",
        "Start",
        "End",
    ]
    assert more_info_row_names == expected_row_names


def test_schematisation_file_info_model_more_section_rows():
    model = SchematisationFileInfoModel(
        descriptor=None, file_data={"data_type": "threedi_schematisation"}
    )
    more_info_row_names = [row.key for row in model.get_more_section().rows]
    expected_row_names = [
        "Projection",
        "Type",
        "Status",
        "Schematisation name",
        "Schematisation ID",
        "Schematisation description",
        "Schematisation created by",
        "Schematisation created on",
        "Schematisation tags",
        "Latest revision ID",
        "Latest revision number",
        "Latest revision valid",
        "Latest revision is simulation ready",
        "Node count",
        "Line count",
    ]
    assert more_info_row_names == expected_row_names


@pytest.mark.parametrize(
    "user_dict, expected_username",
    [
        (None, None),
        ({}, None),
        ({"given_name": "foo"}, "foo"),
        ({"family_name": "bar"}, "bar"),
        ({"given_name": "foo", "family_name": "bar"}, "foo bar"),
    ],
)
def test_file_info_model_username(user_dict, expected_username):
    user = FileInfoModel.username(user_dict)
    assert user.value == expected_username


def test_file_info_model_general():
    descriptor = {"description": "test123"}
    file_data = {
        "data_type": "vector",
        "size": 12,
        "user": {"given_name": "foo", "family_name": "bar"},
        "id": "bar/foo.gpkg",
        "last_modified": "2019-08-24T14:15:22Z",
    }
    model = FileInfoModel(descriptor=descriptor, file_data=file_data)
    general_info = model.get_general_info()
    # check general info
    assert general_info == model.get_general_info()
    assert general_info.filename.value == "foo.gpkg"
    assert general_info.icon_name == "vector"
    assert general_info.size.value == "12.0 Bytes"
    assert general_info.user.value == "foo bar"
    assert general_info.avatar_user == file_data["user"]
    assert general_info.message.value == "test123"
    assert general_info.last_modified.value == "24-08-2019 14:15"


@pytest.mark.parametrize(
    "status_field, status_msg",
    [
        ({"id": "complete"}, "complete"),
        (
            {"id": "failed", "message_i18n": {"msg": "Something went wrong"}},
            "failed: Something went wrong",
        ),
    ],
)
def test_file_info_model_more_info(status_field, status_msg):
    descriptor = {"status": status_field, "description": "test123"}
    file_data = {
        "data_type": "vector",
        "size": 12,
        "user": {},
        "id": "bar/foo.gpkg",
        "last_modified": "2019-08-24T14:15:22Z",
    }
    model = FileInfoModel(descriptor=descriptor, file_data=file_data)
    more_info = model.get_more_section()
    row_dict = {row.key: row.value for row in more_info.rows}
    assert row_dict["Status"].value == status_msg
    assert row_dict["Storage"].value == "12.0 Bytes"
    assert row_dict["Type"].value == "vector"


def test_scenario_file_info_model_more_info():
    descriptor = {
        "status": {"id": "completed"},
        "meta": {
            "simulation": {
                "name": "Flood run",
                "id": 1337,
                "interval": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
                "software": {"id": "3di", "version": "2"},
            },
            "schematisation": {
                "name": "Model",
                "id": "schema-1",
                "version": 1,
                "revision_id": 2,
                "model_id": 42,
            },
        },
    }
    model = ScenarioFileInfoModel(descriptor=descriptor, file_data=None)
    row_dict = {row.key: row.value for row in model.get_more_section().rows}
    assert row_dict["Simulation name"].value == "Flood run"
    assert row_dict["Simulation ID"].value == 1337
    assert row_dict["Schematisation name"].value == "Model"
    assert row_dict["Schematisation ID"].value == "schema-1"
    assert row_dict["Schematisation version"].value == 1
    assert row_dict["Revision ID"].value == 2
    assert row_dict["Model ID"].value == 42
    assert row_dict["Model software"].value == "3di"
    assert row_dict["Software version"].value == "2"
    assert row_dict["Start"].value == "01-01-2026 00:00"
    assert row_dict["End"].value == "01-01-2026 01:00"


def test_schematisation_file_info_model_more_info():
    schematisation_data = {
        "schematisation": {
            "name": "Model",
            "id": "schema-1",
            "version": 1,
            "meta": {"description": "foo"},
            "tags": ["foo", "bar"],
            "created": "2026-07-09T11:40:20.413840Z",
            "created_by_first_name": "a",
            "created_by_last_name": "user",
        },
        "latest_revision": {"id": 123, "number": 2, "is_valid": True},
    }
    threedi_model = MagicMock(nodes_count=100, lines_count=200)
    model = SchematisationFileInfoModel(
        descriptor=None,
        file_data=None,
        schematisation_data=schematisation_data,
        threedi_model_data=threedi_model,
    )
    row_dict = {row.key: row.value for row in model.get_more_section().rows}
    assert row_dict["Schematisation name"].value == "Model"
    assert row_dict["Schematisation ID"].value == "schema-1"
    assert row_dict["Schematisation description"].value == "foo"
    assert row_dict["Schematisation created by"].value == "a user"
    assert row_dict["Schematisation created on"].value == "09-07-2026 11:40"
    assert row_dict["Schematisation tags"].value == "foo; bar"
    assert row_dict["Latest revision ID"].value == 123
    assert row_dict["Latest revision number"].value == 2
    assert row_dict["Latest revision valid"].value == True
    assert row_dict["Latest revision is simulation ready"].value == True
    assert row_dict["Node count"].value == 100
    assert row_dict["Line count"].value == 200


def test_schematisation_file_info_model_more_info_no_valid_model():
    model = SchematisationFileInfoModel(
        descriptor=None, file_data=None, schematisation_data={}, threedi_model_data=None
    )
    row_dict = {row.key: row.value for row in model.get_more_section().rows}
    assert row_dict["Latest revision is simulation ready"].value == False


@pytest.mark.parametrize("crs_parent", ["extent", "grid"])
def test_file_info_model_get_projection(crs_parent):
    descriptor = {"meta": {crs_parent: {"crs": "EPSG:32631"}}}
    model = FileInfoModel(descriptor=descriptor, file_data=None)
    assert model.get_projection().value == "EPSG:32631"


def test_schematisation_file_info_model_get_projection():
    descriptor = {"meta": {"extent": {"crs": "EPSG:32631"}}}
    schematisation_data = {
        "latest_revision": {
            "rasters": [{"type": "foo"}, {"type": "dem_file", "epsg_code": "32630"}]
        }
    }
    model_no_schematisation_data = SchematisationFileInfoModel(
        descriptor=descriptor, file_data=None, schematisation_data=None
    )
    model_with_schematisation_data = SchematisationFileInfoModel(
        descriptor=descriptor, file_data=None, schematisation_data=schematisation_data
    )
    assert model_no_schematisation_data.get_projection().value == "EPSG:32631"
    assert model_with_schematisation_data.get_projection().value == "EPSG:32630"


def test_schematisation_file_info_model_related_files():
    descriptor = {
        "schematisation": {"name": "Model", "tags": ["urban", "demo"]},
        "latest_revision": {
            "sqlite": {"file": {"filename": "model.sqlite", "size": 12}},
            "is_simulation_ready": True,
        },
    }
    model = SchematisationFileInfoModel(
        descriptor=None, file_data=None, schematisation_data=descriptor
    )
    assert [row.name.value for row in model.get_related_files()] == [
        "model.sqlite",
        "gridadmin.h5",
        "gridadmin.gpkg",
    ]
