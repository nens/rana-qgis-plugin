from unittest.mock import MagicMock

from rana_qgis_plugin.simulation.threedi_calls import ThreediCalls


def test_fetch_organisations_filters_organisation_objects():
    api = MagicMock()
    calls = ThreediCalls(api)
    organisations = [
        MagicMock(unique_id="allowed"),
        MagicMock(unique_id="other"),
    ]
    calls.paginated_fetch = MagicMock(return_value=organisations)

    result = calls.fetch_organisations(["allowed"])

    assert result == [organisations[0]]


def test_fetch_organisations_without_filter_returns_all_objects():
    api = MagicMock()
    calls = ThreediCalls(api)
    organisations = [MagicMock(unique_id="allowed")]
    calls.paginated_fetch = MagicMock(return_value=organisations)

    assert calls.fetch_organisations() == organisations
