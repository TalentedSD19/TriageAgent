"""Jira: create an issue, add a comment."""

import os

import requests
from dotenv import load_dotenv

load_dotenv()

TIMEOUT = 30
PRIORITY_NAMES = {"high": "High", "medium": "Medium", "low": "Low"}


def _base() -> str:
    return os.environ["JIRA_URL"].rstrip("/")


def _auth() -> tuple[str, str]:
    return os.environ["JIRA_EMAIL"], os.environ["JIRA_API_TOKEN"]


def _adf(text: str) -> dict:
    """Jira Cloud needs rich text in Atlassian Document Format: one paragraph per line."""
    paragraphs = [
        {"type": "paragraph", "content": [{"type": "text", "text": line}]} if line else {"type": "paragraph"}
        for line in text.splitlines()
    ]
    return {"type": "doc", "version": 1, "content": paragraphs or [{"type": "paragraph"}]}


def _post(path: str, payload: dict) -> requests.Response:
    return requests.post(f"{_base()}{path}", json=payload, auth=_auth(), timeout=TIMEOUT)


def _raise_for(response: requests.Response) -> None:
    if not response.ok:
        raise RuntimeError(f"Jira {response.status_code}: {response.text[:500]}")


def issue_url(key: str) -> str:
    return f"{_base()}/browse/{key}"


def create_issue(title: str, description: str, priority: str, reporter_email: str) -> str:
    """Create a Bug and return its key, e.g. 'OPS-12'."""
    fields = {
        "project": {"key": os.environ["JIRA_PROJECT_KEY"]},
        "issuetype": {"name": "Bug"},
        "summary": title[:255],
        "description": _adf(f"{description}\n\nReported by: {reporter_email}"),
        "priority": {"name": PRIORITY_NAMES.get(priority, "Medium")},
    }
    response = _post("/rest/api/3/issue", {"fields": fields})
    # Some projects hide the priority field on the create screen; retry without it.
    if response.status_code == 400 and '"priority"' in response.text:
        del fields["priority"]
        response = _post("/rest/api/3/issue", {"fields": fields})
    _raise_for(response)
    return response.json()["key"]


def add_comment(key: str, text: str) -> None:
    _raise_for(_post(f"/rest/api/3/issue/{key}/comment", {"body": _adf(text)}))


def check_connection() -> None:
    _raise_for(requests.get(f"{_base()}/rest/api/3/myself", auth=_auth(), timeout=TIMEOUT))


if __name__ == "__main__":
    key = create_issue(
        "TriageAgent test issue",
        "Created by jira_client.py to check the connection. Safe to delete.",
        "low",
        os.getenv("GMAIL_ADDRESS", "test@example.com"),
    )
    add_comment(key, "Test comment from TriageAgent.")
    print(f"Created {key}: {issue_url(key)}")
