# Job-Hunt Assistant (Responsible Mode)

A personal job-search **assistant** for freshers targeting IT/Software roles. It
aggregates jobs from **ToS-friendly public sources**, AI-scores them for fit,
filters out fake "entry-level" postings, drafts personalised cold mails for your
review, detects walk-in drives, and tracks everything in a color-coded Excel
workbook — all controllable from your phone via Telegram.

## Why "responsible mode"?

This project deliberately **does not** log into LinkedIn / Naukri / Indeed /
Shine, drive a hidden browser, simulate human input to dodge bot-detection, or
auto-submit applications. Those platforms forbid automation in their Terms of
Service and routinely **permanently ban** accounts caught doing it — a far
bigger setback for a fresher than the time saved. Mass auto-applying and
cold-email blasting also read as spam to recruiters.

Instead this tool:

- pulls jobs only from **documented public APIs and RSS feeds** (Remotive,
  RemoteOK, and any RSS feed you add);
- does the tedious work — scoring, filtering, deduping, resume selection,
  tracking — automatically;
- keeps **you** in the loop for the irreversible/outward-facing steps: you click
  *Submit* on applications, and **no cold mail is sent without your approval**.

You keep ~90% of the convenience without risking your accounts or reputation.

## File structure

```
job_automation/
├── main.py                      # entry point (manual + scheduler + CLI)
├── requirements.txt
├── .env.example                 # copy to .env and fill in secrets
├── config/
│   ├── config.py                # all settings, templates, weights
│   ├── resumes/                 # drop resume_python.pdf etc. here
│   ├── blacklist.txt            # companies to never apply to
│   └── whitelist.txt            # priority companies
├── ai/
│   ├── job_scorer.py            # keyword-weighted relevance score (1–10)
│   └── hr_name_extractor.py     # pull HR name from JD for personalisation
├── sources/                     # ToS-friendly job sources (no scraping evasion)
│   ├── base_source.py           # shared filter→score→route pipeline
│   ├── remotive_source.py       # Remotive public API
│   ├── remoteok_source.py       # RemoteOK public API
│   ├── rss_source.py            # any RSS feed you configure
│   └── registry.py
├── mailers/
│   ├── cold_mailer.py           # draft / approve / rate-limited Gmail sender
│   └── followup_mailer.py       # auto follow-up after N days
├── tracker/
│   ├── excel_tracker.py         # 7-sheet color-coded workbook
│   ├── status_manager.py        # pipeline status updates
│   ├── cooldown_manager.py      # company cooldown + black/whitelist
│   └── job_applications.xlsx    # auto-created on first run
├── telegram_bot/
│   ├── bot.py                   # full remote-control bot
│   └── notifier.py              # one-shot push messages (run summaries/alerts)
├── reports/
│   └── weekly_report.py         # weekly summary, auto every Sunday
├── utils/
│   ├── fresher_filter.py        # reject fake entry-level JDs
│   ├── resume_selector.py       # pick the right resume per JD
│   ├── email_extractor.py       # find HR email, skip generic inboxes
│   ├── walkin_detector.py       # detect + parse walk-in drives
│   ├── rate_limiter.py          # per-source daily caps
│   └── logger.py                # colored console + rotating file logs
└── logs/                        # rotating logs, session/limit/cooldown JSON
```

> The Telegram package is named `telegram_bot` (not `telegram`) so it doesn't
> shadow the `python-telegram-bot` library's own `telegram` module.

## Setup

1. **Install dependencies** (Python 3.10+):
   ```bash
   pip install -r requirements.txt
   ```
2. **Configure secrets**: copy `.env.example` to `.env` and fill it in.
   ```bash
   cp .env.example .env
   ```
3. **Gmail App Password** (for cold mail): enable 2-Step Verification, then
   create an App Password at <https://myaccount.google.com/apppasswords> and put
   the 16-character value in `GMAIL_APP_PASSWORD`. Never use your normal Gmail
   password.
4. **Telegram bot**: message [@BotFather](https://t.me/BotFather) → `/newbot` →
   copy the token into `TELEGRAM_BOT_TOKEN`. Get your chat id from
   [@userinfobot](https://t.me/userinfobot) and put it in `TELEGRAM_CHAT_ID`
   (the bot only responds to this id).
5. **Resumes**: drop your PDF into `config/resumes/` and point the paths in
   `RESUMES` (`config/config.py`) at it. A single resume is fine — set all
   variants to the same file. With `USE_RESUME_PROFILE=True` (default) the bot
   parses this PDF to learn your real skills and uses them to search + score.
6. **Job sources**: Remotive and RemoteOK work out of the box. Add any career
   page / aggregator RSS feeds to `SOURCES["rss"]["feeds"]` in `config.py`.
7. **Gmail job-alert source (LinkedIn / Naukri / Indeed) — the safe way to get
   those platforms' jobs.** See the dedicated section below.

## Getting LinkedIn / Naukri / Indeed jobs safely (Gmail alerts)

The bot **never logs into or scrapes** LinkedIn/Naukri/Indeed — doing so
violates their terms and gets accounts banned. Instead it reads **your own
inbox** for the job-alert emails those sites send you, and feeds them through
the same scoring/filtering/tracking pipeline. You apply on the site yourself
(one click). This is fully within the rules: you're only reading your own mail.

**One-time setup:**

1. **Turn on IMAP in Gmail**: Settings → *Forwarding and POP/IMAP* → *Enable
   IMAP* → Save. (The `GMAIL_APP_PASSWORD` you already created works for IMAP.)
2. **Create job alerts on each platform** (use your real, normal account — no
   automation):
   - **LinkedIn**: run a job search (e.g. *AI Engineer · India · Entry level*) →
     toggle **Set alert** → in *Job alerts* settings choose **Email**, daily.
   - **Naukri / Indeed**: do the same — save the search and pick **email** alerts.
3. That's it. The sites email matching jobs to your Gmail; the bot parses them on
   the next run. Configure which senders to read and how far back to look in
   `SOURCES["gmail"]` in `config.py`.

> Alert emails only carry the job title/company/location (not the full
> description), so these jobs are treated as **pre-qualified** — they came from
> criteria *you* set, so the bot won't reject them on a thin-text score. It
> dedupes them, scores them for sorting, filters obvious senior roles, and logs
> them to **Manual Apply Needed** for you to open and apply.

### Safety rails (in `.env`)

| Variable               | Default | Effect                                                        |
|------------------------|---------|---------------------------------------------------------------|
| `DRY_RUN`              | `true`  | Cold mails are written to `data/drafts/` instead of sent.     |
| `REQUIRE_MAIL_CONFIRM` | `true`  | Mails are queued; nothing sends until you `--send-approved`.  |

Set both to `false` only when you're confident and want unattended sending
(still capped by `MAX_COLD_MAILS_PER_DAY`, default 15).

## Running

```bash
python main.py                    # one run across all enabled sources
python main.py --source remotive  # run a single source
python main.py --schedule         # run daily at the configured times
python main.py --followups-only   # only process due follow-ups
python main.py --status           # print the pipeline summary
python main.py --send-approved    # send all queued cold mails (after review)
python main.py --send-approved 5  # send up to 5
python main.py --report           # generate (and push) the weekly report

python -m telegram_bot.bot        # start the Telegram remote control
python -m webapp                  # start the local web dashboard (127.0.0.1:8000)
```

## Web dashboard (local)

A small FastAPI + Jinja dashboard that wraps the existing tracker so you can
work from the browser instead of opening Excel:

- **Browse & click jobs** — Manual Apply Needed and Walk-In Drives as cards with
  an **Open ↗** button that takes you straight to the posting.
- **Mark applied** — moves a manual job into *Applied Jobs* (calls `log_applied`)
  in one click.
- **Approve cold mails** — review the queue and send (calls `send_approved`).
- **Run now** — triggers `run_all()` in the background; the page polls and
  refreshes when the run finishes.

```bash
pip install -r requirements.txt   # adds fastapi, uvicorn, jinja2
python -m webapp                  # open http://127.0.0.1:8000
```

It binds to `127.0.0.1` with **no authentication** — it's a local single-user
tool. Don't expose it to the network without adding a login. As with any
openpyxl write, close `job_applications.xlsx` in Excel before using the
*Mark applied* / status / approve actions (the UI shows a friendly message if
the file is locked).

## Excel workbook (7 sheets)

| # | Sheet                | Purpose                                                        |
|---|----------------------|----------------------------------------------------------------|
| 1 | Dashboard            | Totals, response rate, best source, last-updated timestamp.    |
| 2 | Applied Jobs         | Jobs you've submitted; status dropdown + AI-score color bands. |
| 3 | Walk-In Drives       | Detected walk-ins with date/time/venue.                        |
| 4 | Manual Apply Needed  | High-fit jobs for you to review and submit.                    |
| 5 | Cold Mails Sent      | Cold mails (draft/queued/sent) with follow-up dates.           |
| 6 | Follow-Ups           | Follow-ups that have been sent.                                |
| 7 | Skipped Jobs         | Every skipped job + reason (transparency).                     |

Update an application's status from code:
```python
from tracker.status_manager import update_status
update_status("https://job/url", "Interview Scheduled")
```

## Telegram commands

`/start` · `/help` · `/run [source]` · `/status` · `/walkins` · `/manual` ·
`/followups` · `/skipped` · `/approve [N]` · `/stop`

The bot ignores every chat except your `TELEGRAM_CHAT_ID`.

## Decision flow

```
Job fetched from a public source
        │
Walk-in drive?            ──YES──▶ Walk-In Drives sheet
        │ NO
Company blacklisted?      ──YES──▶ Skipped (Blacklisted)
        │ NO
Company on cooldown?      ──YES──▶ Skipped (Cooldown)
        │ NO
Fake entry-level?         ──YES──▶ Skipped (Fake Entry Level)
        │ NO
Already in tracker (URL)? ──YES──▶ Skipped (Duplicate)
        │ NO
AI score < MIN_AI_SCORE?  ──YES──▶ Skipped (Low Score)
        │ NO
Source daily cap hit?     ──YES──▶ Skipped (Rate Limit)
        │ NO
Pick resume (Python/Java/Fullstack from JD)
        │
HR email in the JD?       ──YES──▶ Draft/queue cold mail (you approve)
        │ NO
Manual Apply Needed sheet (you review & click Submit)
```

## Troubleshooting

- **Gmail auth error**: you must use an App Password, not your account password,
  and 2-Step Verification must be enabled first.
- **No jobs found**: public APIs are remote-focused; broaden `JOB_KEYWORDS` or
  add India-specific RSS feeds in `config.py`.
- **Telegram bot silent**: confirm `TELEGRAM_CHAT_ID` matches your account — the
  bot deliberately ignores all other chats.
- **Excel locked**: close `job_applications.xlsx` in Excel before a run; openpyxl
  can't write to an open file on Windows.

## Notes & limits

- Follow-ups are capped at one per cold mail (tracked by the sheet's
  *Follow-Up Sent* column).
- The AI scorer is a transparent keyword-weighted heuristic, not an LLM call —
  fast, free, and offline. Tune `SKILL_WEIGHTS` in `ai/job_scorer.py`.
- Want more sources? Subclass `BaseSource`, implement `fetch_jobs()`, and
  register it in `sources/registry.py`. Please keep new sources to documented
  public APIs / feeds.
```
