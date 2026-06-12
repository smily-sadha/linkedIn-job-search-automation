"""FastAPI app: a local dashboard over the job-hunt assistant.

Page routes (server-rendered, share one app shell):
    GET  /            Overview (triage: attention items + KPIs)
    GET  /manual      Manual Apply Needed (full list)
    GET  /walkins     Walk-In Drives
    GET  /cold-mails  Cold mails awaiting approval
    GET  /applied     Applied jobs (with status management)

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
def manual_page(request: Request, msg: str | None = None, err: str | None = None):
    return _render("manual.html", _ctx(
        request, "manual", "Manual Apply Needed",
        "High-fit jobs to review and submit", msg=msg, err=err,
        manual=repo.manual_jobs(),
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
