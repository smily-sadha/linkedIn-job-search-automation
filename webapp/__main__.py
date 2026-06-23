"""Launch the dashboard:  python -m webapp  (http://127.0.0.1:8000).

Host/port are configurable via env vars so you can change them without editing
code — e.g. run on a different port if 8000 is busy:
    WEBAPP_PORT=8800 python -m webapp        (or set WEBAPP_PORT in .env)
"""
import os
import socket
import sys

import uvicorn


def _find_free_port(host: str, start_port: int, max_tries: int = 10) -> int | None:
    for candidate in range(start_port, start_port + max_tries):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, candidate))
                return candidate
            except OSError:
                continue
    return None


if __name__ == "__main__":
    host = os.getenv("WEBAPP_HOST", "127.0.0.1")
    port = int(os.getenv("WEBAPP_PORT", "8000"))
    print(f"Dashboard starting at http://{host}:{port}")
    try:
        uvicorn.run("webapp.app:app", host=host, port=port, log_level="info")
    except OSError as exc:
        if exc.errno in (98, 10048):
            alt_port = _find_free_port(host, port + 1)
            if alt_port is not None:
                print(
                    f"Port {port} is busy. Falling back to http://{host}:{alt_port}."
                )
                uvicorn.run("webapp.app:app", host=host, port=alt_port, log_level="info")
                sys.exit(0)
            print(
                f"ERROR: Cannot bind to {host}:{port} because the port is already in use."
            )
            print(
                "Use WEBAPP_PORT=<another-port> or stop the process already using port 8000."
            )
            sys.exit(1)
        raise
