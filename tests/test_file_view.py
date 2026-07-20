import pytest

from rana_qgis_plugin.widgets.file_view import FieldValue


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


@pytest.mark.parametrize(
    "func,exp_error,exp_val",
    [
        (lambda: {"key": "val"}, False, {"key": "val"}),
        (lambda: None, True, None),
    ],
)
def test_field_value_from_call(func, exp_error, exp_val):
    fv = FieldValue.from_call(func)
    assert fv.error is exp_error
    assert fv.value == exp_val


def test_field_value_from_call_raises():
    def boom():
        raise RuntimeError("something went wrong")

    fv = FieldValue.from_call(boom)
    assert fv.error is True
    assert "something went wrong" in fv.error_msg
