"""Runs the loop: read -> understand -> ticket -> reply.

uv run main.py           # run the agent, checking the inbox every 60 seconds
uv run main.py --once    # handle the current unread emails, then stop
uv run main.py --check   # check the logins for OpenAI, Gmail, Jira and ServiceNow
"""

import argparse
import os
import time
from datetime import datetime

from dotenv import load_dotenv

import jira_client
import mail
import memory
import servicenow_client
from understand import Details, understand
from understand import check_connection as check_openai

load_dotenv()

POLL_SECONDS = 60
TEST_MODE = os.getenv("TEST_MODE", "true").strip().lower() not in ("false", "0", "no")

# In TEST_MODE emails are never marked read, so remember them here to avoid repeating work.
_seen_in_test_mode: set[str] = set()


def log(message: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] {message}", flush=True)


def create_ticket(email: mail.Email, details: Details) -> tuple[str, str, str, str]:
    """Return (system, ticket number, id used for comments, link)."""
    description = details.summary
    if details.error_messages:
        description += "\n\nError messages:\n" + "\n".join(f"- {m}" for m in details.error_messages)
    description += f"\n\nOriginal email:\n{email.body}"

    if details.type == "incident":
        number, sys_id = servicenow_client.create_incident(details.title, description, details.priority, email.sender)
        return "servicenow", number, sys_id, servicenow_client.incident_url(sys_id)
    key = jira_client.create_issue(details.title, description, details.priority, email.sender)
    return "jira", key, key, jira_client.issue_url(key)


def add_comment(record: dict, email: mail.Email) -> None:
    text = f"Update from {email.sender}:\n\n{email.body}"
    if record["system"] == "servicenow":
        servicenow_client.add_comment(record["id"], text)
    else:
        jira_client.add_comment(record["id"], text)


def handle(email: mail.Email) -> None:
    log(f"New email from {email.sender}: {email.subject!r}")

    if memory.already_handled(email.thread_id, email.message_id):
        log("  Already handled earlier; marking as read")
        mail.mark_read(email)
        return

    record = memory.get(email.thread_id)
    if record:
        # A reply in a thread that already has a ticket: always keep it on that ticket.
        log(f"  Reply to a thread with ticket {record['ticket']} ({record['system']})")
        if TEST_MODE:
            log(f"  TEST_MODE: would add a comment to {record['ticket']} and reply to the sender")
            return
        add_comment(record, email)
        memory.add_message(email.thread_id, email.message_id)
        log(f"  Added comment to {record['ticket']}")
        mail.send_reply(email, f"Thanks, your update was added to ticket {record['ticket']}.")
        log("  Replied to sender")
        mail.mark_read(email)
        log("  Marked as read")
        return

    details = understand(email.subject, email.body)
    log(f"  OpenAI: {details.model_dump_json()}")

    if not details.is_problem:
        log("  Not a problem report; ignoring")
        if not TEST_MODE:
            mail.mark_read(email)
        return

    target = "ServiceNow incident" if details.type == "incident" else "Jira bug"
    if TEST_MODE:
        log(f"  TEST_MODE: would create a {target} ({details.priority}) and reply to the sender")
        return

    system, ticket, ticket_id, link = create_ticket(email, details)
    memory.save(email.thread_id, system, ticket, ticket_id, email.message_id)
    log(f"  Created {target} {ticket} ({details.priority}): {link}")
    mail.send_reply(
        email,
        f"Thanks for your report. We have logged it as ticket {ticket}:\n\n{details.title}\n\n"
        "Reply to this email to add more details to the same ticket.",
    )
    log("  Replied to sender")
    mail.mark_read(email)
    log("  Marked as read")


def run_once() -> None:
    emails = [e for e in mail.fetch_unread() if e.uid not in _seen_in_test_mode]
    if emails:
        log(f"{len(emails)} unread email(s)")
    for email in emails:
        if TEST_MODE:
            _seen_in_test_mode.add(email.uid)
        try:
            handle(email)
        except Exception as error:  # noqa: BLE001 - keep going; the email stays unread and is retried next round
            log(f"  ERROR: {error}")


def check() -> None:
    for name, test in [
        ("OpenAI", check_openai),
        ("Gmail", mail.check_connection),
        ("Jira", jira_client.check_connection),
        ("ServiceNow", servicenow_client.check_connection),
    ]:
        try:
            test()
            print(f"OK    {name}")
        except Exception as error:  # noqa: BLE001 - report every failing service, not just the first
            print(f"FAIL  {name}: {error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="TriageAgent: turn support emails into tickets.")
    parser.add_argument("--once", action="store_true", help="handle the current unread emails, then stop")
    parser.add_argument("--check", action="store_true", help="check the logins for all services")
    args = parser.parse_args()

    if args.check:
        check()
        return

    log(f"TriageAgent started (TEST_MODE={'on' if TEST_MODE else 'off'})")
    while True:
        try:
            run_once()
        except Exception as error:  # noqa: BLE001 - e.g. Gmail briefly unreachable
            log(f"ERROR reading inbox: {error}")
        if args.once:
            break
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Stopped")
