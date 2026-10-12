"""ServiceNow: create an incident, add a comment."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 30
URGENCY = {"high": "1", "medium": "2", "low": "3"}
HEADERS = {"Accept": "application/json", "Content-Type": "application/json"}


def _base() -> str:
    return os.environ["SERVICENOW_URL"].rstrip("/")


def _auth() -> tuple[str, str]:
    return os.environ["SERVICENOW_USER"], os.environ["SERVICENOW_PASSWORD"]


def _raise_for(response: requests.Response) -> None:
    if not response.ok:
        raise RuntimeError(f"ServiceNow {response.status_code}: {response.text[:500]}")


def incident_url(sys_id: str) -> str:
    return f"{_base()}/nav_to.do?uri=incident.do?sys_id={sys_id}"


def create_incident(title: str, description: str, priority: str, reporter_email: str) -> tuple[str, str]:
    """Create an incident and return (number, sys_id), e.g. ('INC0010001', '6f1e...')."""
    level = URGENCY.get(priority, "2")
    payload = {
        "short_description": title[:160],
        "description": f"{description}\n\nReported by: {reporter_email}",
        "urgency": level,
        # ServiceNow derives priority from urgency x impact, so set both for a matching priority.
        "impact": level,
    }
    response = requests.post(
        f"{_base()}/api/now/table/incident", json=payload, auth=_auth(), headers=HEADERS, timeout=TIMEOUT
    )
    _raise_for(response)
    result = response.json()["result"]
    return result["number"], result["sys_id"]


def add_comment(sys_id: str, text: str) -> None:
    """Add a customer-visible comment (the 'Additional comments' journal field)."""
    response = requests.patch(
        f"{_base()}/api/now/table/incident/{sys_id}",
        json={"comments": text},
        auth=_auth(),
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    _raise_for(response)


def check_connection() -> None:
    response = requests.get(
        f"{_base()}/api/now/table/incident",
        params={"sysparm_limit": 1, "sysparm_fields": "number"},
        auth=_auth(),
        headers=HEADERS,
        timeout=TIMEOUT,
    )
    _raise_for(response)


if __name__ == "__main__":
    number, sys_id = create_incident(
        "TriageAgent test incident",
        "Created by servicenow_client.py to check the connection. Safe to delete.",
        "low",
        os.getenv("GMAIL_ADDRESS", "test@example.com"),
    )
    add_comment(sys_id, "Test comment from TriageAgent.")
    print(f"Created {number}: {incident_url(sys_id)}")
