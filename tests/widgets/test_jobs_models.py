from unittest.mock import patch

import pytest

from rana_qgis_plugin.widgets.jobs_models import (
    JobData,
    JobParseError,
    build_job_link_html,
    job_can_be_cancelled,
)


def test_job_data_parses_api_response_and_display_fields():
    job = JobData.from_job_dict(
        {
            "id": 42,
            "name": "Simulation job",
            "creator": {"given_name": "Test", "family_name": "User"},
            "created_at": "2026-10-29T12:00:00Z",
            "state": {"type": "running", "progress": 0.25},
            "process": {"id": "tracker", "name": "Simulation tracker"},
            "inputs": {"simulation_id": 123},
        }
    )

    assert job.id == 42
    assert job.progress == 25
    assert job.max_progress == 100
    assert job.process_id == "tracker"
    assert job.process_name == "Simulation tracker"
    assert job.progress_str() == "running (25%)"
    assert job.user_name == "Test User"
    assert job.created_timestamp > 0


def test_job_data_handles_missing_process():
    job = JobData.from_job_dict(
        {
            "id": 42,
            "name": "Standalone job",
            "creator": {"given_name": "Test", "family_name": "User"},
            "created_at": "2026-10-29T12:00:00Z",
            "state": {"type": "completed", "progress": 1},
            "process": None,
            "inputs": {},
        }
    )

    assert job.process_id is None
    assert job.process_name is None


def make_job(status: str = "running", process_id: str | None = "tracker") -> JobData:
    return JobData(
        id=42,
        name="Simulation job",
        user={"given_name": "Test", "family_name": "User"},
        created="2026-10-29T12:00:00Z",
        status=status,
        progress=25,
        max_progress=100,
        process_id=process_id,
        process_name="Simulation tracker",
        inputs={"simulation_id": 123},
    )


@pytest.mark.parametrize("status_type", ["running", "completed"])
@pytest.mark.parametrize("process_id", ["tracker", "other"])
def test_job_can_be_cancelled(status_type, process_id):
    can_be_cancelled = (process_id == "tracker") and (status_type == "running")
    job = make_job(status=status_type, process_id=process_id)
    assert job_can_be_cancelled(job, "tracker") == can_be_cancelled


def test_build_job_link_html_links_jobs_with_process_id():
    with (
        patch(
            "rana_qgis_plugin.widgets.jobs_models.base_url",
            return_value="https://rana.test",
        ),
        patch(
            "rana_qgis_plugin.widgets.jobs_models.get_tenant_id", return_value="tenant"
        ),
    ):
        link = build_job_link_html(make_job(), "project-slug")

    assert link == (
        '<a href="https://rana.test/tenant/projects/project-slug?tab=2&job=42">'
        "Simulation job</a>"
    )


def test_build_job_link_html_returns_plain_name_without_process():
    assert (
        build_job_link_html(make_job(process_id=None), "project-slug")
        == "Simulation job"
    )


VALID_JOB = {
    "id": 42,
    "name": "Simulation job",
    "creator": {"given_name": "Test", "family_name": "User"},
    "created_at": "2026-10-29T12:00:00Z",
    "state": {"type": "running", "progress": 0.25},
    "process": None,
    "inputs": {},
}


@pytest.mark.parametrize(
    "job",
    [
        {**VALID_JOB, "state": None},
        {**VALID_JOB, "state": {"type": "running"}},
        {**VALID_JOB, "process": {"name": "Tracker"}},
        {k: v for k, v in VALID_JOB.items() if k != "inputs"},
        {k: v for k, v in VALID_JOB.items() if k != "created_at"},
    ],
    ids=["state-null", "state-no-progress", "process-no-id", "no-inputs", "no-created"],
)
def test_job_data_raises_parse_error_for_malformed_payload(job):
    with pytest.raises(JobParseError):
        JobData.from_job_dict(job)
