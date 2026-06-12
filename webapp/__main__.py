"""Launch the dashboard:  python -m webapp  (http://127.0.0.1:8000)."""
import uvicorn

if __name__ == "__main__":
    # Local-only bind, no reload (keeps the single background-run state intact).
    uvicorn.run("webapp.app:app", host="127.0.0.1", port=8000, log_level="info")
