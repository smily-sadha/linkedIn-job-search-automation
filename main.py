"""
Entry point for the job-hunt assistant (responsible mode).

What a run does:
  1. init_excel()         - ensure the tracker exists
  2. send_followups()     - chase unanswered cold mails (if any are due)
  3. fetch from enabled, ToS-friendly sources (public APIs + RSS)
  4. filter -> AI-score -> route each job:
        walk-in        -> Walk-In Drives sheet
        cold-mailable  -> queued/drafted cold mail (you approve before send)
        otherwise      -> Manual Apply Needed (you review & click submit)
  5. refresh_dashboard()  - recompute Sheet 1

Nothing logs into LinkedIn/Naukri/etc., and no mail is sent without your
explicit approval (unless you turn the safety rails off in .env).

Usage:
    python main.py                       # one run, all sources
    python main.py --source remotive     # one source only
    python main.py --schedule            # run on the daily schedule
    python main.py --followups-only      # just process due follow-ups
    python main.py --status              # print pipeline summary
    python main.py --send-approved [N]   # send queued cold mails (after review)
    python main.py --report              # generate + (try to) send weekly report
"""
import argparse
import time
from datetime import datetime

import schedule

from config.config import SCHEDULE_TIMES, WEEKLY_REPORT_DAY, WEEKLY_REPORT_TIME
from mailers import cold_mailer
from mailers.followup_mailer import send_followups
from sources.registry import available_keys, get_sources
from tracker.excel_tracker import init_excel, refresh_dashboard
from utils.logger import get_logger

logger = get_logger("main")


def run_all(source: str = "all") -> dict:
    """Run enabled sources, route results, return a summary dict."""
    start = time.monotonic()
    summary = {
        "found": 0, "queued_manual": 0, "walkins": 0, "cold_mails": 0,
        "skipped": 0, "errors": 0, "duration_seconds": 0,
    }
    try:
        init_excel()
        fup = send_followups()
        logger.info("Follow-ups: %s", fup)

        for src in get_sources(only=source, mailer=cold_mailer):
            try:
                s = src.run()
                summary["found"] += s.get("fetched", 0)
                summary["queued_manual"] += s.get("queued_manual", 0)
                summary["walkins"] += s.get("walkins", 0)
                summary["cold_mails"] += s.get("cold_mails", 0)
                summary["skipped"] += s.get("skipped", 0)
                summary["errors"] += s.get("errors", 0)
            except Exception as exc:  # one source failing never stops the rest
                summary["errors"] += 1
                logger.error("Source '%s' crashed: %s", getattr(src, "name", "?"), exc, exc_info=True)

        refresh_dashboard()
    except Exception as exc:
        summary["errors"] += 1
        logger.error("run_all failed: %s", exc, exc_info=True)

    summary["duration_seconds"] = round(time.monotonic() - start, 1)
    logger.info("RUN COMPLETE: %s", summary)
    _maybe_notify(summary)
    return summary


def _maybe_notify(summary: dict) -> None:
    """Best-effort Telegram run summary; never fatal if Telegram isn't set up."""
    try:
        from telegram_bot.notifier import send_run_summary
        send_run_summary(summary)
    except Exception as exc:
        logger.info("Telegram notify skipped: %s", exc)


def run_scheduled() -> None:
    for t in SCHEDULE_TIMES:
        schedule.every().day.at(t).do(run_all)
    try:
        from reports.weekly_report import generate_weekly_report
        getattr(schedule.every(), WEEKLY_REPORT_DAY).at(WEEKLY_REPORT_TIME).do(generate_weekly_report)
    except Exception as exc:
        logger.warning("Weekly report not scheduled: %s", exc)

    logger.info("Scheduler started. Run times: %s. Ctrl+C to stop.", SCHEDULE_TIMES)
    while True:
        schedule.run_pending()
        time.sleep(30)


def print_status() -> None:
    from tracker.status_manager import get_pipeline_summary
    init_excel()
    summary = get_pipeline_summary()
    print(f"\nJob Hunt Status - {datetime.now():%d %b %Y}\n" + "-" * 32)
    for status, count in summary.items():
        print(f"  {status:<22} {count}")
    pending = len(cold_mailer.list_pending())
    if pending:
        print(f"\n  {pending} cold mail(s) awaiting approval (--send-approved)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Job-hunt assistant (responsible mode)")
    parser.add_argument("--schedule", action="store_true", help="run on the daily schedule")
    parser.add_argument("--source", default="all",
                        help=f"source to run: all | {' | '.join(available_keys())}")
    parser.add_argument("--followups-only", action="store_true", help="only process due follow-ups")
    parser.add_argument("--status", action="store_true", help="print pipeline summary and exit")
    parser.add_argument("--send-approved", nargs="?", const=-1, type=int, metavar="N",
                        help="send up to N queued cold mails (all if N omitted)")
    parser.add_argument("--report", action="store_true", help="generate weekly report")
    args = parser.parse_args()

    if args.status:
        print_status()
    elif args.followups_only:
        init_excel()
        print(send_followups())
    elif args.send_approved is not None:
        init_excel()
        limit = None if args.send_approved == -1 else args.send_approved
        print(cold_mailer.send_approved(limit=limit))
    elif args.report:
        from reports.weekly_report import generate_weekly_report
        print(generate_weekly_report())
    elif args.schedule:
        run_scheduled()
    else:
        print(run_all(source=args.source))


if __name__ == "__main__":
    main()
