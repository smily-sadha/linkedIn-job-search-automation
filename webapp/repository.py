"""Read/write access to the Excel workbook for the web UI.

Everything here is a thin wrapper over the existing tracker so the web layer
never re-implements business logic. Reads use read_only workbooks; the few
writes reuse the same openpyxl path the rest of the app uses.

Note (Windows): openpyxl cannot write while the workbook is open in Excel.
Write helpers raise WorkbookLocked so the UI can show a friendly message.
"""
from datetime import date

from openpyxl import load_workbook

from config.config import EXCEL_FILE
from mailers import cold_mailer
from tracker.excel_tracker import (
    HEADERS, S_APPLIED, S_MANUAL, S_WALKIN, init_excel, log_applied,
    refresh_dashboard,
)
from tracker.status_manager import get_pipeline_summary, update_status
from utils.logger import get_logger

logger = get_logger("webapp.repository")


class WorkbookLocked(Exception):
    """Raised when the workbook can't be written (usually open in Excel)."""


def _rows_as_dicts(sheet: str) -> list[dict]:
    """Return every non-empty data row of `sheet` as a header-keyed dict."""
    init_excel()
    headers = HEADERS[sheet]
    wb = load_workbook(EXCEL_FILE, read_only=True)
    ws = wb[sheet]
    out: list[dict] = []
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not any(row):
            continue
        out.append({h: row[i] if i < len(row) else None for i, h in enumerate(headers)})
    wb.close()
    return out


# ── Reads ─────────────────────────────────────────────────────────────────────
def manual_jobs(include_done: bool = False) -> list[dict]:
    """Jobs in 'Manual Apply Needed'. By default only those still Pending."""
    rows = _rows_as_dicts(S_MANUAL)
    if include_done:
        return rows
    return [r for r in rows if str(r.get("Status", "")).strip().lower() == "pending"]


def walkins() -> list[dict]:
    return _rows_as_dicts(S_WALKIN)


def applied_jobs() -> list[dict]:
    return _rows_as_dicts(S_APPLIED)


def pipeline_summary() -> dict:
    return get_pipeline_summary()


def pending_cold_mails() -> list[dict]:
    return cold_mailer.list_pending()


def counts() -> dict:
    """Headline numbers for the dashboard cards."""
    return {
        "manual_pending": len(manual_jobs()),
        "walkins": len(walkins()),
        "applied": len(applied_jobs()),
        "cold_pending": len(pending_cold_mails()),
    }


# ── Writes ──────────────────────────────────────────────────────────────────--
def _set_status_by_url(sheet: str, url_header: str, status_header: str,
                       url: str, new_status: str) -> bool:
    """Set the status cell of the row whose URL column matches `url`."""
    headers = HEADERS[sheet]
    url_col = headers.index(url_header) + 1
    status_col = headers.index(status_header) + 1
    try:
        wb = load_workbook(EXCEL_FILE)
    except PermissionError as exc:
        raise WorkbookLocked("Close job_applications.xlsx in Excel and try again.") from exc
    ws = wb[sheet]
    for r in range(2, ws.max_row + 1):
        if ws.cell(row=r, column=url_col).value == url:
            ws.cell(row=r, column=status_col, value=new_status)
            wb.save(EXCEL_FILE)
            return True
    return False


def mark_manual_applied(url: str) -> bool:
    """Move a 'Manual Apply Needed' job into 'Applied Jobs' and mark it done."""
    if not url:
        return False
    job = next((j for j in manual_jobs(include_done=True)
                if j.get("Job URL") == url), None)
    if job is None:
        logger.warning("mark_manual_applied: url not found %s", url)
        return False
    log_applied({
        "company": job.get("Company Name", ""),
        "title": job.get("Job Title", ""),
        "location": job.get("Location", ""),
        "source": job.get("Source", ""),
        "url": url,
        "notes": "Marked applied from web UI",
    })
    _set_status_by_url(S_MANUAL, "Job URL", "Status", url, "Applied")
    refresh_dashboard()
    return True


def set_applied_status(url: str, new_status: str) -> bool:
    """Update the Status of a row in 'Applied Jobs' (reuses status_manager)."""
    try:
        ok = update_status(url, new_status)
    except PermissionError as exc:
        raise WorkbookLocked("Close job_applications.xlsx in Excel and try again.") from exc
    if ok:
        refresh_dashboard()
    return ok


def approve_cold_mails(limit: int | None = None) -> dict:
    return cold_mailer.send_approved(limit=limit)
