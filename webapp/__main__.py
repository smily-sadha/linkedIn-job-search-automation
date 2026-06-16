"""Launch the dashboard:  python -m webapp  (http://127.0.0.1:8000).

Host/port are configurable via env vars so you can change them without editing
code — e.g. run on a different port if 8000 is busy:
    WEBAPP_PORT=8800 python -m webapp        (or set WEBAPP_PORT in .env)
"""
import os

import uvicorn

if __name__ == "__main__":
    host = os.getenv("WEBAPP_HOST", "127.0.0.1")
    port = int(os.getenv("WEBAPP_PORT", "8000"))
    # Local-only bind, no reload (keeps the single background-run state intact).
    print(f"Dashboard starting at http://{host}:{port}")
    uvicorn.run("webapp.app:app", host=host, port=port, log_level="info")
