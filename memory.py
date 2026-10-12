"""Remembers which email thread maps to which ticket (a small JSON file).

Shape: {"<thread_id>": {"system": "jira", "ticket": "OPS-12", "id": "OPS-12", "messages": [...]}}
"id" is what the ticket system needs to add a comment (the Jira key, or the ServiceNow sys_id).
"messages" lists the email Message-IDs already handled, so no email is acted on twice.
"""

import json
import os
from pathlib import Path

PATH = Path(__file__).parent / "memory.json"


def _load() -> dict:
    if not PATH.exists():
        return {}
    return json.loads(PATH.read_text(encoding="utf-8"))


def _save(data: dict) -> None:
    tmp = PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
    os.replace(tmp, PATH)


def get(thread_id: str) -> dict | None:
    return _load().get(thread_id)


def save(thread_id: str, system: str, ticket: str, ticket_id: str, message_id: str) -> None:
    data = _load()
    data[thread_id] = {"system": system, "ticket": ticket, "id": ticket_id, "messages": [message_id]}
    _save(data)


def add_message(thread_id: str, message_id: str) -> None:
    data = _load()
    data[thread_id]["messages"].append(message_id)
    _save(data)


def already_handled(thread_id: str, message_id: str) -> bool:
    record = get(thread_id)
    return record is not None and message_id in record["messages"]
