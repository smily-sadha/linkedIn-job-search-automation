"""FastAPI app: a local dashboard over the job-hunt assistant.

Page routes (server-rendered, share one app shell):
    GET  /            Overview (triage: attention items + KPIs)
    GET  /manual      Manual Apply Needed (full list)
    GET  /walkins     Walk-In Drives
    GET  /cold-mails  Cold mails awaiting approval
    GET  /applied     Applied jobs (with status management)
    GET  /history     Applied jobs grouped by day (timeline)

Action routes (POST, redirect back with a flash message):
    POST /manual/mark-applied  move a manual job into Applied Jobs
    POST /applied/status       update an applied job's status
    POST /cold-mails/approve   send queued cold mails (optionally up to N)
    POST /run                  trigger a pipeline run in the background
    GET  /run-status           JSON: {running, summary} for live polling

Local-only by design — binds to 127.0.0.1 with no auth. Do not expose publicly
without adding authentication.
"""
from pathlib import Path
from urllib.parse import urlencode

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from tracker.excel_tracker import VALID_STATUSES
from webapp import repository as repo
from webapp import runner

_TEMPLATES = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

app = FastAPI(title="Job-Hunt Assistant")

# Friendly labels for the "Run now" source picker. Keys match registry source
# names; "all" runs every enabled source.
_SOURCE_LABELS = {
    "all": "All sources", "linkedin": "LinkedIn", "naukri": "Naukri",
    "indeed": "Indeed", "remotive": "Remotive", "remoteok": "RemoteOK",
    "gmail": "Gmail alerts", "rss": "RSS feeds", "walkin_search": "Walk-in search",
}


def _source_options() -> list[dict]:
    """[{key,label}] for the Run-now dropdown: 'All' plus each enabled source."""
    from config.config import SOURCES
    from sources.registry import available_keys
    enabled = [k for k in available_keys() if SOURCES.get(k, {}).get("enabled")]
    keys = ["all"] + enabled
    return [{"key": k, "label": _SOURCE_LABELS.get(k, k.title())} for k in keys]


@app.on_event("startup")
def _start_scheduler() -> None:
    """Kick off the daily auto-fetch when the server boots."""
    from webapp import scheduler
    scheduler.start()


def _ctx(request: Request, active: str, title: str, subtitle: str = "",
         msg: str | None = None, err: str | None = None, **extra) -> dict:
    """Shared template context: nav state, run state, flash, counts."""
    base = {
        "request": request,
        "active": active,
        "title": title,
        "subtitle": subtitle,
        "counts": repo.counts(),
        "running": runner.is_running(),
        "last_run": runner.last_summary(),
        "sources": _source_options(),
        "msg": msg,
        "err": err,
    }
    base.update(extra)
    return base


def _render(name: str, ctx: dict) -> HTMLResponse:
    return _TEMPLATES.TemplateResponse(name, ctx)


# ── Pages ───────────────────────────────────────────────────────────────────--
@app.get("/", response_class=HTMLResponse)
def overview(request: Request, msg: str | None = None, err: str | None = None):
    manual = repo.manual_jobs()
    walks = repo.walkins()
    cold = repo.pending_cold_mails()
    return _render("overview.html", _ctx(
        request, "overview", "Overview", "What needs your attention today",
        msg=msg, err=err,
        summary=repo.pipeline_summary(),
        top_manual=manual[:5],
        upcoming_walkins=walks[:3],
        cold_preview=cold[:3],
    ))


@app.get("/manual", response_class=HTMLResponse)
def manual_page(request: Request, msg: str | None = None, err: str | None = None,
                new: str | None = None, fresh: str | None = None,
                source: str | None = None):
    new_only = new in ("1", "true", "yes")
    fresh_only = fresh in ("1", "true", "yes")
    jobs = repo.manual_jobs(new_only=new_only, fresh_only=fresh_only)
    # Per-platform tabs are computed before the source filter so each tab keeps
    # its full count regardless of which one is currently selected.
    tabs = repo.source_tabs(jobs)
    source = (source or "").strip().lower() or None
    if source:
        jobs = [j for j in jobs if repo.source_key(j) == source]
    qs = []
    if fresh_only:
        qs.append("fresh=1")
    if new_only:
        qs.append("new=1")
    if source:
        qs.append(f"source={source}")
    origin = "/manual" + ("?" + "&".join(qs) if qs else "")
    return _render("manual.html", _ctx(
        request, "manual", "Manual Apply Needed",
        "High-fit jobs to review and submit", msg=msg, err=err,
        manual=jobs, new_only=new_only, fresh_only=fresh_only,
        source_tabs=tabs, source=source, origin=origin,
    ))


@app.get("/walkins", response_class=HTMLResponse)
def walkins_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("walkins.html", _ctx(
        request, "walkins", "Walk-In Drives", "Detected walk-in opportunities",
        msg=msg, err=err, walkins=repo.walkins(),
    ))


@app.get("/cold-mails", response_class=HTMLResponse)
def cold_mails_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("cold_mails.html", _ctx(
        request, "cold-mails", "Cold Mails", "Drafted mails awaiting your approval",
        msg=msg, err=err, cold_mails=repo.pending_cold_mails(),
    ))


@app.get("/applied", response_class=HTMLResponse)
def applied_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("applied.html", _ctx(
        request, "applied", "Applied Jobs", "Track where each application stands",
        msg=msg, err=err, applied=repo.applied_jobs(), statuses=VALID_STATUSES,
    ))


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("history.html", _ctx(
        request, "history", "Application History",
        "Everything you've applied to, grouped by day", msg=msg, err=err,
        groups=repo.applied_history(),
    ))


@app.get("/insights", response_class=HTMLResponse)
def insights_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("insights.html", _ctx(
        request, "insights", "What's Working",
        "Where your replies actually come from", msg=msg, err=err,
        data=repo.insights(),
    ))


@app.get("/tailor", response_class=HTMLResponse)
def tailor_page(request: Request, url: str = "", msg: str | None = None,
                err: str | None = None):
    job = repo.manual_job_by_url(url)
    result, note = None, None
    if job is None:
        note = "Job not found — it may have been applied to or deleted."
    else:
        from ai.groq_client import is_enabled
        if not is_enabled():
            note = "LLM is off. Set USE_LLM_SCORING=true and GROQ_API_KEY in .env to use tailoring."
        else:
            from ai.tailor import tailor_application
            result = tailor_application(job)
            if result is None:
                note = "The LLM couldn't generate this right now — try again in a moment."
    return _render("tailor.html", _ctx(
        request, "manual", "Tailor Application",
        (job["Job Title"] if job else ""), msg=msg, err=err,
        job=job, result=result, note=note,
    ))


# ── Actions ─────────────────────────────────────────────────────────────────--
def _back(to: str = "/", msg: str = "", err: str = "") -> RedirectResponse:
    params = {k: v for k, v in (("msg", msg), ("err", err)) if v}
    url = to + (("?" + urlencode(params)) if params else "")
    return RedirectResponse(url=url, status_code=303)


@app.post("/manual/mark-applied")
def mark_applied(url: str = Form(...)):
    try:
        ok = repo.mark_manual_applied(url)
    except repo.WorkbookLocked as exc:
        return _back("/manual", err=str(exc))
    return _back("/manual", msg="Moved to Applied." if ok else "Job not found.")


@app.post("/manual/dismiss")
def dismiss(url: str = Form(...)):
    try:
        ok = repo.dismiss_manual(url)
    except repo.WorkbookLocked as exc:
        return _back("/manual", err=str(exc))
    return _back("/manual", msg="Dismissed." if ok else "Job not found.")


@app.post("/manual/verify")
def verify_status(origin: str = Form("/manual")):
    try:
        r = repo.verify_manual_status()
    except Exception as exc:
        return _back(origin, err=f"Verify failed: {exc}")
    return _back(origin, msg=f"Checked {r['checked']}: {r['open']} open, "
                 f"{r['closed']} closed, {r['unknown']} unknown.")


@app.post("/manual/clear-closed")
def clear_closed(origin: str = Form("/manual")):
    try:
        n = repo.clear_closed_manual()
    except repo.WorkbookLocked as exc:
        return _back(origin, err=str(exc))
    return _back(origin, msg=f"Cleared {n} closed job(s)." if n
                 else "No closed jobs to clear.")


@app.post("/manual/clear-all")
def clear_all(origin: str = Form("/manual")):
    try:
        n = repo.clear_all_manual()
    except repo.WorkbookLocked as exc:
        return _back(origin, err=str(exc))
    return _back(origin, msg=f"Cleared all {n} job(s) from the list." if n
                 else "List is already empty.")


@app.post("/manual/delete")
def manual_delete(url: str = Form(...), origin: str = Form("/manual")):
    try:
        ok = repo.delete_by_url(repo.S_MANUAL, url)
    except repo.WorkbookLocked as exc:
        return _back(origin, err=str(exc))
    return _back(origin, msg="Deleted." if ok else "Job not found.")


@app.post("/walkins/delete")
def walkin_delete(url: str = Form(...), origin: str = Form("/walkins")):
    try:
        ok = repo.delete_by_url(repo.S_WALKIN, url)
    except repo.WorkbookLocked as exc:
        return _back(origin, err=str(exc))
    return _back(origin, msg="Deleted." if ok else "Walk-in not found.")


@app.post("/applied/delete")
def applied_delete(url: str = Form(...), origin: str = Form("/applied")):
    try:
        ok = repo.delete_by_url(repo.S_APPLIED, url)
    except repo.WorkbookLocked as exc:
        return _back(origin, err=str(exc))
    return _back(origin, msg="Deleted." if ok else "Application not found.")


@app.post("/cold-mails/delete")
def cold_mail_delete(email: str = Form(...), company: str = Form("")):
    ok = repo.discard_cold_mail(email, company)
    return _back("/cold-mails", msg="Draft deleted." if ok else "Draft not found.")


@app.post("/applied/status")
def applied_status(url: str = Form(...), status: str = Form(...)):
    try:
        ok = repo.set_applied_status(url, status)
    except repo.WorkbookLocked as exc:
        return _back("/applied", err=str(exc))
    return _back("/applied", msg=f"Status set to {status}." if ok else "Could not update.")


@app.post("/cold-mails/approve")
def approve(limit: str = Form("")):
    n = int(limit) if limit.strip().isdigit() else None
    result = repo.approve_cold_mails(limit=n)
    return _back("/cold-mails",
                 msg=f"Sent {result['sent']}, failed {result['failed']}, "
                     f"{result['remaining']} left.")


@app.post("/run")
def run(source: str = Form("all"), origin: str = Form("/")):
    started = runner.start_run(source=source)
    return _back(origin, msg="Run started — this can take a minute."
                 if started else "A run is already in progress.")


@app.get("/run-status")
def run_status():
    return JSONResponse({"running": runner.is_running(), "summary": runner.last_summary()})
