"""Local web dashboard for the job-hunt assistant.

A thin FastAPI layer over the existing Excel tracker and mailer so you can
browse + click jobs, update status, approve cold mails, and trigger a run from
the browser instead of the CLI/Excel. Run with:

    python -m webapp        # http://127.0.0.1:8000
"""
