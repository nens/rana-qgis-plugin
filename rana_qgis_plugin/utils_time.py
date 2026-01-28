from datetime import datetime, timezone

from dateutil import parser
from dateutil.relativedelta import relativedelta
from qgis.PyQt.QtCore import Qt

from rana_qgis_plugin.utils import NumericItem


def convert_to_numeric_timestamp(timestamp: str) -> float:
    if timestamp.endswith("Z"):
        timestamp = timestamp.replace("Z", "+00:00")
    dt = datetime.fromisoformat(timestamp)
    return dt.timestamp()


def parse_timestamp_str(timestamp: str) -> datetime:
    return parser.isoparse(timestamp)


def convert_timestamp_str_to_local_time(timestamp: str) -> str:
    time = parse_timestamp_str(timestamp)
    return convert_timestamp_to_local_time(time)


def convert_timestamp_to_local_time(time: datetime) -> str:
    return time.astimezone().strftime("%d-%m-%Y %H:%M")


def convert_timestamp_str_to_relative_time(timestamp: str) -> str:
    past = parse_timestamp_str(timestamp)
    return convert_timestamp_to_relative_time(past)


def convert_timestamp_to_relative_time(past: datetime) -> str:
    """Convert a timestamp into a relative time string."""
    now = datetime.now(timezone.utc)
    delta = relativedelta(now, past)

    if delta.years > 0:
        return f"{delta.years} year{'s' if delta.years > 1 else ''} ago"
    elif delta.months > 0:
        return f"{delta.months} month{'s' if delta.months > 1 else ''} ago"
    elif delta.days > 0:
        return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
    elif delta.hours > 0:
        return f"{delta.hours} hour{'s' if delta.hours > 1 else ''} ago"
    elif delta.minutes > 0:
        return f"{delta.minutes} minute{'s' if delta.minutes > 1 else ''} ago"
    else:
        return "Just now"


def format_activity_timestamp_str(timestamp: str) -> str:
    past = parse_timestamp_str(timestamp)
    return format_activity_timestamp(past)


def format_activity_timestamp(past: datetime) -> str:
    now = datetime.now(timezone.utc)
    if (now - past).days < 5:
        return convert_timestamp_to_relative_time(past)
    else:
        return convert_timestamp_to_local_time(past)


def get_timestamp_as_numeric_item(timestamp_str: str) -> NumericItem:
    timestamp = convert_to_numeric_timestamp(timestamp_str)
    display_timestamp = format_activity_timestamp_str(timestamp_str)
    local_timestamp = convert_timestamp_str_to_local_time(timestamp_str)
    item = NumericItem(display_timestamp)
    item.setData(timestamp, role=Qt.ItemDataRole.UserRole)
    if display_timestamp != local_timestamp:
        item.setToolTip(local_timestamp)
    return item
