import pytest

from rana_qgis_plugin.widgets.file_info_models import (
    FieldValue,
    FileInfoModel,
    ScenarioFileInfoModel,
    SchematisationFileInfoModel,
    get_file_info_model_class,
)


@pytest.mark.parametrize(
    "dict_data,key,exp_error,exp_val",
    [
        ({"foo": "bar"}, "foo", False, "bar"),
        ({"foo": "bar"}, "missing", True, None),
        (None, "foo", True, None),
        ({}, "foo", True, "fallback"),
    ],
)
def test_field_value_from_dict(dict_data, key, exp_error, exp_val):
    fv = FieldValue.from_dict(dict_data, key, default="fallback")
    assert fv.error is exp_error
    if exp_error:
        assert fv.value == "fallback"
    else:
        assert fv.value == exp_val


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


def test_scenario_model_contains_simulation_information():
    model = ScenarioFileInfoModel(
        descriptor={
            "meta": {
                "simulation": {
                    "name": "Flood run",
                    "interval": ["2026-01-01T00:00:00Z", "2026-01-01T01:00:00Z"],
                    "software": {"id": "3di", "version": "2"},
                },
                "schematisation": {"name": "Base", "id": "schema-1"},
            }
        }
    )
    row_dict = {row.key: row.value for row in model.get_more_section().rows}
    assert row_dict["Simulation name"].value == "Flood run"
    assert row_dict["Model software"].value == "3di"
    assert isinstance(row_dict["Start"].value, str)


def test_schematisation_model_contains_related_files():
    descriptor = {
        "schematisation": {"name": "Model", "tags": ["urban", "demo"]},
        "latest_revision": {
            "sqlite": {"file": {"filename": "model.sqlite", "size": 12}},
            "is_simulation_ready": True,
        },
    }
    model = SchematisationFileInfoModel(descriptor=descriptor)

    model.schematisation_data = descriptor
    assert [row.name.value for row in model.get_related_files()] == [
        "model.sqlite",
        "gridadmin.h5",
        "gridadmin.gpkg",
    ]


def test_generic_model_has_separate_general_data():
    model = FileInfoModel(
        descriptor=None, file_data={"id": "file.txt", "data_type": "other", "size": 12}
    )
    general = model.get_general_info()
    assert general.filename.value == "file.txt"
    assert general.size.value == "12.0 Bytes"
