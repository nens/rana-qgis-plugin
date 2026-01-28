from datetime import datetime, timezone

import pytest
from freezegun import freeze_time

from rana_qgis_plugin.utils_time import (
    convert_timestamp_str_to_local_time,
    convert_timestamp_str_to_relative_time,
    convert_to_numeric_timestamp,
    format_activity_timestamp_str,
)


def test_convert_to_timestamp():
    timstamp_str = "2023-01-01T12:00:00Z"
    ref_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert ref_time.timestamp() == convert_to_numeric_timestamp(timstamp_str)


def test_convert_to_local_time():
    timstamp_str = "2023-01-01T12:00:00Z"
    assert "01-01-2023 12:00" == convert_timestamp_str_to_local_time(timstamp_str)


@pytest.mark.parametrize(
    "timestamp_str, expected_relative_time",
    [
        ("2023-01-10T12:00:00Z", "Just now"),
        ("2023-01-10T11:59:00Z", "1 minute ago"),
        ("2023-01-10T11:50:00Z", "10 minutes ago"),
        ("2023-01-10T11:00:00Z", "1 hour ago"),
        ("2023-01-10T10:00:00Z", "2 hours ago"),
        ("2023-01-09T12:00:00Z", "1 day ago"),
        ("2023-01-08T12:00:00Z", "2 days ago"),
        ("2022-12-10T12:00:00Z", "1 month ago"),
        ("2022-11-10T12:00:00Z", "2 months ago"),
        ("2021-10-10T12:00:00Z", "1 year ago"),
        ("2021-01-07T12:00:00Z", "2 years ago"),
    ],
)
@freeze_time("2023-01-10T12:00:00Z")
def test_convert_to_relative_time(timestamp_str, expected_relative_time):
    assert (
        convert_timestamp_str_to_relative_time(timestamp_str) == expected_relative_time
    )


@pytest.mark.parametrize(
    "timestamp_str",
    ["2022-01-10T12:00:00Z", "2022-12-10T12:00:00Z", "2023-01-05T12:00:00Z"],
)
@freeze_time("2023-01-10T12:00:00Z")
def test_format_activity_time_to_absolute(timestamp_str):
    assert format_activity_timestamp_str(
        timestamp_str
    ) == convert_timestamp_str_to_local_time(timestamp_str)


@pytest.mark.parametrize(
    "timestamp_str", ["2023-01-10T12:00:00Z", "2023-01-06T11:59:59Z"]
)
@freeze_time("2023-01-10T12:00:00Z")
def test_format_activity_time_to_relative(timestamp_str):
    assert format_activity_timestamp_str(
        timestamp_str
    ) == convert_timestamp_str_to_relative_time(timestamp_str)
