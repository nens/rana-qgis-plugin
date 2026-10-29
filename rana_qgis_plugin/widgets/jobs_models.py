from dataclasses import dataclass

from rana_qgis_plugin.utils.settings import base_url, get_tenant_id
from rana_qgis_plugin.utils.time import convert_to_numeric_timestamp


class JobParseError(ValueError):
    """Raised when a job API response cannot be parsed into JobData."""


@dataclass
class JobData:
    """Represent a Rana job in the Processes UI."""

    id: int
    name: str
    user: dict
    created: str
    status: str
    progress: int
    max_progress: int
    process_id: str | None
    process_name: str | None
    inputs: dict

    def progress_str(self) -> str:
        """Return the display string for the job progress."""
        return f"{self.status} ({self.progress}%)"

    @property
    def created_timestamp(self) -> float:
        """Return the job creation time as a numeric timestamp."""
        return convert_to_numeric_timestamp(self.created)

    @property
    def user_name(self) -> str:
        """Return the job creator's display name."""
        return f"{self.user['given_name']} {self.user['family_name']}"

    @classmethod
    def from_job_dict(cls, job: dict) -> "JobData":
        """Parse a Rana job API response into display data.

        Raises JobParseError when the response is missing expected fields.
        """
        try:
            process: dict | None = job["process"]
            state = job["state"]
            return cls(
                id=job["id"],
                name=job["name"],
                user=job["creator"],
                created=job["created_at"],
                status=state["type"],
                progress=int(100 * state["progress"]),
                max_progress=100,
                process_id=process["id"] if process is not None else None,
                process_name=process["name"] if process is not None else None,
                inputs=job["inputs"],
            )
        except (KeyError, TypeError, ValueError) as error:
            raise JobParseError(f"Unexpected job data: {error!r}") from error


def job_can_be_cancelled(
    job: JobData, simulation_tracker_process_id: str | None
) -> bool:
    """Return whether the job is a running simulation-tracker process."""
    return job.status == "running" and job.process_id == simulation_tracker_process_id


def build_job_link_html(job: JobData, project_slug: str) -> str:
    """Build the legacy Processes-tab link, or plain name when unlinked."""
    if not job.process_id:
        return job.name
    job_url = (
        f"{base_url()}/{get_tenant_id()}/projects/{project_slug}?tab=2&job={job.id}"
    )
    return f'<a href="{job_url}">{job.name}</a>'
