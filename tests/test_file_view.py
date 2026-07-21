from unittest.mock import MagicMock

import pytest

from rana_qgis_plugin.widgets.file_view import FieldValue


def make_comm():
    comm = MagicMock()
    return comm


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
    comm = make_comm()
    fv = FieldValue.from_call(func, comm)
    assert fv.error is exp_error
    assert fv.value == exp_val


def test_field_value_from_call_raises():
    def boom():
        raise RuntimeError("something went wrong")

    comm = make_comm()
    fv = FieldValue.from_call(boom, comm)
    assert fv.error is True
    assert "something went wrong" in fv.error_msg


def test_field_value_from_call_returns_error_on_none():
    comm = make_comm()
    result = FieldValue.from_call(lambda: None, comm)
    assert result.error is True
    comm.log_err.assert_not_called()


def test_field_value_from_call_logs_on_exception():
    def boom():
        raise RuntimeError("oops")

    comm = make_comm()
    FieldValue.from_call(boom, comm)
    comm.log_err.assert_called_once()


def test_field_value_from_call_no_log_on_success():
    comm = make_comm()
    FieldValue.from_call(lambda: {"ok": True}, comm)
    comm.log_err.assert_not_called()
    comm.log_warn.assert_not_called()
