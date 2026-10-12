# TriageAgent

Reads emails from a support inbox and, when one reports a problem, creates a ticket in
**Jira** (bugs) or **ServiceNow** (incidents) using the OpenAI API. See [plan.md](plan.md).

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync                  # create .venv and install dependencies
cp .env.example .env     # fill in credentials
uv run main.py
```

`TEST_MODE=true` prints what would happen without creating real tickets.

## Checking each part

```bash
uv run main.py --check          # log in to OpenAI, Gmail, Jira and ServiceNow
uv run mail.py                  # print unread emails
uv run understand.py            # print OpenAI's answer for each file in sample_emails/
uv run jira_client.py           # create a test Jira bug with a comment
uv run servicenow_client.py     # create a test ServiceNow incident with a comment
uv run main.py --once           # handle the current unread emails once, then stop
```

Thread-to-ticket links are saved in `memory.json`. Delete it to start fresh.
