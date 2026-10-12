# TriageAgent

Reads emails from a support inbox and, when one reports a problem, creates a ticket in
**Jira** (bugs) or **ServiceNow** (incidents) using the OpenAI API, then replies to the
sender with the ticket number. See [plan.md](plan.md) for the design.

```
Send an email → the agent picks it up → a ticket appears in Jira or ServiceNow → the agent replies with the ticket number
```

## Contents

1. [Install the tools](#1-install-the-tools)
2. [Create the accounts](#2-create-the-accounts)
3. [Fill in `.env`](#3-fill-in-env)
4. [Check the logins](#4-check-the-logins)
5. [Test each part](#5-test-each-part)
6. [Run the agent](#6-run-the-agent)
7. [Run the demo](#7-run-the-demo)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Install the tools

You need **Python 3.11+**, **git**, and **[uv](https://docs.astral.sh/uv/)**.

Install uv:

```bash
# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Get the code and install the dependencies:

```bash
git clone https://github.com/TalentedSD19/TriageAgent.git
cd TriageAgent
uv sync                  # creates .venv and installs everything
```

You don't need to activate the virtual environment: `uv run ...` uses it automatically.

---

## 2. Create the accounts

You need four accounts. All of them have a free option, but OpenAI needs a few dollars
of credit.

### 2.1 Gmail (the support inbox)

Use a **new Gmail account just for testing**, not your personal one.

1. Create the Gmail account.
2. Turn on **2-Step Verification**: [myaccount.google.com](https://myaccount.google.com) →
   **Security** → **2-Step Verification**. App Passwords only work once this is on.
3. Create an **App Password**: go to
   [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords), type a
   name (e.g. `TriageAgent`) and click **Create**.
4. Copy the 16-character password and remove the spaces.
5. IMAP is on by default for Gmail. If your settings still show an IMAP switch
   (⚙ → **See all settings** → **Forwarding and POP/IMAP**), make sure it is enabled.

You will also need **a second email account** (any provider) to send the test emails from.

### 2.2 Jira

1. Go to [atlassian.com](https://www.atlassian.com/software/jira/free), choose **Jira**,
   and sign up for the free plan. Your site will be `https://<yoursite>.atlassian.net`.
2. **Create a project** with the **Scrum** or **Bug tracking** template. These include the
   **Bug** issue type, which the agent needs.
3. Note the **project key**: the short code in front of issue numbers (e.g. `OPS` in
   `OPS-1`), also shown under **Project settings**.
4. Create an **API token**: go to
   [id.atlassian.com/manage-profile/security/api-tokens](https://id.atlassian.com/manage-profile/security/api-tokens)
   → **Create API token** (the plain one, not "with scopes"). Name it and **copy it right
   away**, because it is shown only once.

### 2.3 ServiceNow

1. Sign up at [developer.servicenow.com](https://developer.servicenow.com).
2. Click **Request Instance** and pick the latest release. It can take a few minutes.
3. When it is ready, note the **instance URL** (`https://devXXXXX.service-now.com`), the
   **username** (`admin`) and the **password**. If the password isn't shown, use
   **Manage instance password**.
4. Open the URL in your browser and log in once to check it works.

Free instances go to sleep when idle (wake them from the developer portal), and are
reclaimed after about 10 days without use.

### 2.4 OpenAI

1. Go to [platform.openai.com/api-keys](https://platform.openai.com/api-keys) →
   **Create new secret key**, and copy it.
2. Add some credit under **Settings → Billing**. $5 is plenty; API calls fail without it.

---

## 3. Fill in `.env`

Copy the template:

```bash
cp .env.example .env     # Windows PowerShell: Copy-Item .env.example .env
```

Open `.env` and fill in the values from step 2:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=                         # blank = gpt-5.4-mini

GMAIL_ADDRESS=yourtestinbox@gmail.com
GMAIL_APP_PASSWORD=abcdefghijklmnop   # 16 characters, no spaces

JIRA_URL=https://yoursite.atlassian.net
JIRA_EMAIL=the-email-you-signed-up-with
JIRA_API_TOKEN=...
JIRA_PROJECT_KEY=OPS

SERVICENOW_URL=https://dev12345.service-now.com
SERVICENOW_USER=admin
SERVICENOW_PASSWORD=...

TEST_MODE=true
```

`.env` is in `.gitignore`. Never commit it or share it.

---

## 4. Check the logins

```bash
uv run main.py --check
```

Expected:

```
OK    OpenAI
OK    Gmail
OK    Jira
OK    ServiceNow
```

If any line says `FAIL`, see [Troubleshooting](#8-troubleshooting).

---

## 5. Test each part

Each file can be run on its own:

| Command | What it does | Expected result |
|---|---|---|
| `uv run mail.py` | Prints the unread emails in the inbox | Subject and body of each test email |
| `uv run understand.py` | Sends each file in `sample_emails/` to OpenAI | The JSON result for each one |
| `uv run jira_client.py` | Creates a test Bug with a comment | A new issue appears in Jira |
| `uv run servicenow_client.py` | Creates a test incident with a comment | A new incident appears in ServiceNow |

`mail.py` and `understand.py` only read; they don't change anything. The two client
scripts create real tickets, which you can delete afterwards.

---

## 6. Run the agent

### Dry run first

With `TEST_MODE=true` the agent prints what it **would** do but changes nothing: no
tickets, no replies, and emails stay unread.

```bash
uv run main.py --once    # handle the current unread emails once, then stop
```

### Real run

Set `TEST_MODE=false` in `.env`, then:

```bash
uv run main.py           # checks the inbox every 60 seconds; Ctrl+C to stop
uv run main.py --once    # or: one pass, then stop
```

For each unread email the agent:

1. Sends it to OpenAI to decide whether it reports a problem, and of which type.
2. Ignores it (and marks it read) if it is not a problem report.
3. Creates a **Jira bug** for `bug` or a **ServiceNow incident** for `incident`.
4. If the email is a reply in a thread that already has a ticket, adds it as a
   **comment** on that ticket instead.
5. Replies to the sender with the ticket number and marks the email as read.

Thread-to-ticket links are saved in `memory.json`. Delete it to start fresh.

---

## 7. Run the demo

1. Delete `memory.json` if it exists, and set `TEST_MODE=false`.
2. Start the agent: `uv run main.py`.
3. From your **second email account**, send the emails below to the Gmail test inbox.
   Copy the subject (first line, without `Subject:`) and the body from each file in
   `sample_emails/`.
4. Emails **3** and **10** are replies: wait until the agent has replied to email 1 (or 2),
   then use **Reply** in that thread and paste the body. Leave out the note in brackets.
5. Show the terminal log, the new tickets in Jira and ServiceNow, and the replies in your
   second account.

Before sending anything, you can check OpenAI's answers for all 15 with
`uv run understand.py`. Emails 3 and 10 are classified there too, but in the real run
they skip OpenAI and become comments.

**Core demo (from the plan)**

| # | File | Tests | Expected result |
|---|---|---|---|
| 1 | `01_payment_500.txt` | Bug with an error code | Jira bug, high priority, and a reply with the ticket number |
| 2 | `02_login_down.txt` | Outage | ServiceNow incident, high priority, and a reply |
| 3 | `03_reply_mobile.txt` | Reply in a Jira thread | Comment on the bug from #1, no new ticket |
| 4 | `04_thanks.txt` | Not a problem | Ignored, no ticket |
| 5 | `05_prompt_injection.txt` | Prompt injection | Ignored, no ticket and no action |

**Extended tests**

| # | File | Tests | Expected result |
|---|---|---|---|
| 6 | `06_csv_export_medium.txt` | Bug with a workaround | Jira bug, **medium** priority |
| 7 | `07_typo_low.txt` | Cosmetic bug | Jira bug, **low** priority |
| 8 | `08_api_503_incident.txt` | Outage with several error messages | ServiceNow incident, high; both errors listed in the ticket |
| 9 | `09_notifications_incident_medium.txt` | Partial outage with a workaround | ServiceNow incident, **medium** |
| 10 | `10_reply_login_still_down.txt` | Reply in a ServiceNow thread, with quoted text | Comment on the incident from #2 with only the new line; quoted text removed |
| 11 | `11_billing_question.txt` | How-to question | Ignored, no ticket |
| 12 | `12_newsletter.txt` | Marketing email | Ignored, no ticket |
| 13 | `13_bug_with_hidden_injection.txt` | Real bug with injected instructions | Jira bug about accented search; the injected instructions are not followed, and priority comes from the bug itself (not "highest") |
| 14 | `14_fake_tag_injection.txt` | Tries to break out of the `<email>` tags | Ignored, no ticket (no "SERVER ON FIRE" incident) |
| 15 | `15_french_bug.txt` | Email in French | Jira bug for the Safari payment page, error message captured |

**Also check**

- Every ticket created gets exactly one reply email with its number.
- Run `uv run main.py --once` again: nothing new happens, because all emails are read.
- `memory.json` lists threads 1, 2, 6, 7, 8, 9, 13 and 15, and threads 1 and 2 each record
  two messages.

OpenAI's priority and type choices for borderline emails (6, 9, 13) can vary. If one
differs, adjust the rules in `INSTRUCTIONS` in `understand.py`.

---

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| `FAIL Gmail` / authentication failed | Use the App Password, not your normal password. Check 2-Step Verification is on and the password has no spaces. |
| `FAIL OpenAI` / model not found | Set `OPENAI_MODEL` to a model your account can use. |
| `FAIL OpenAI` / quota or 429 | Add credit under **Billing**. |
| `FAIL Jira` / 401 | `JIRA_EMAIL` must be your Atlassian login email, and `JIRA_API_TOKEN` a valid token. |
| Jira error mentioning `issuetype` | The project has no **Bug** type. Use a Scrum or Bug tracking project, or add the type in project settings. |
| `FAIL ServiceNow` / timeout or 401 | The instance is asleep. Wake it from developer.servicenow.com, then check the password. |
| A reply created a new ticket instead of a comment | Make sure you used **Reply** in the same thread, and that `memory.json` wasn't deleted in between. |
| Nothing happens | The agent only reads **unread** emails. Check that the test email arrived in the inbox (not spam) and is unread. |

---

## Development

```bash
uv run pre-commit install           # run ruff and file checks on every commit
uv run pre-commit run --all-files   # run them by hand
```
