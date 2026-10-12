"""Read unread emails, send replies, mark as read."""

import os
import re
import smtplib
from dataclasses import dataclass, field
from email.message import EmailMessage
from email.utils import make_msgid

from dotenv import load_dotenv
from imap_tools import AND, MailBox, MailMessageFlags

load_dotenv()

IMAP_HOST = "imap.gmail.com"
SMTP_HOST = "smtp.gmail.com"
REPLY_HEADER = "X-TriageAgent"  # marks our own replies so we never process them


@dataclass
class Email:
    uid: str
    message_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    references: list[str] = field(default_factory=list)


def _login() -> MailBox:
    return MailBox(IMAP_HOST).login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])


def _header(msg, name: str) -> str:
    values = msg.headers.get(name.lower(), ())
    return values[0].strip() if values else ""


def _message_ids(value: str) -> list[str]:
    return re.findall(r"<[^<>]+>", value)


def _thread_id(message_id: str, references: list[str], in_reply_to: str) -> str:
    """The first message of a conversation identifies the thread."""
    if references:
        return references[0]
    if in_reply_to:
        return in_reply_to
    return message_id


def _html_to_text(html: str) -> str:
    html = re.sub(r"(?is)<(script|style).*?</\1>", "", html)
    html = re.sub(r"(?i)<br\s*/?>|</p>|</div>", "\n", html)
    return re.sub(r"<[^>]+>", "", html)


def strip_quoted(text: str) -> str:
    """Keep only the new part of a message, dropping quoted earlier replies."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^On .+ wrote:$", stripped) or stripped.startswith("-----Original Message-----"):
            break
        if re.match(r"^From: .+", stripped) and lines:
            break
        if stripped.startswith(">"):
            continue
        lines.append(line.rstrip())
    return "\n".join(lines).strip()


def _is_automated(msg) -> bool:
    auto = _header(msg, "auto-submitted").lower()
    return bool(_header(msg, REPLY_HEADER)) or (auto != "" and auto != "no")


def fetch_unread() -> list[Email]:
    """Return unread inbox emails. Our own replies and auto-replies are marked read and skipped."""
    emails = []
    with _login() as mailbox:
        for msg in mailbox.fetch(AND(seen=False), mark_seen=False):
            if _is_automated(msg):
                mailbox.flag(msg.uid, MailMessageFlags.SEEN, True)
                continue
            message_id = _header(msg, "message-id") or f"<uid-{msg.uid}@local>"
            references = _message_ids(_header(msg, "references"))
            in_reply_to = next(iter(_message_ids(_header(msg, "in-reply-to"))), "")
            body = msg.text or _html_to_text(msg.html or "")
            emails.append(
                Email(
                    uid=msg.uid,
                    message_id=message_id,
                    thread_id=_thread_id(message_id, references, in_reply_to),
                    sender=msg.from_,
                    subject=msg.subject or "(no subject)",
                    body=strip_quoted(body),
                    references=references,
                )
            )
    return emails


def mark_read(email: Email) -> None:
    with _login() as mailbox:
        mailbox.flag(email.uid, MailMessageFlags.SEEN, True)


def send_reply(email: Email, text: str) -> None:
    """Reply to the sender in the same thread."""
    address = os.environ["GMAIL_ADDRESS"]
    subject = email.subject if email.subject.lower().startswith("re:") else f"Re: {email.subject}"

    reply = EmailMessage()
    reply["From"] = address
    reply["To"] = email.sender
    reply["Subject"] = subject
    reply["Message-ID"] = make_msgid()
    reply["In-Reply-To"] = email.message_id
    reply["References"] = " ".join([*email.references, email.message_id])
    reply["Auto-Submitted"] = "auto-replied"
    reply[REPLY_HEADER] = "reply"
    reply.set_content(text)

    with smtplib.SMTP_SSL(SMTP_HOST, 465) as smtp:
        smtp.login(address, os.environ["GMAIL_APP_PASSWORD"])
        smtp.send_message(reply)


def check_connection() -> None:
    with _login():
        pass


if __name__ == "__main__":
    unread = fetch_unread()
    print(f"{len(unread)} unread email(s)\n")
    for e in unread:
        print(f"From:    {e.sender}\nSubject: {e.subject}\nThread:  {e.thread_id}\n\n{e.body}\n{'-' * 60}")
