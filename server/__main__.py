"""Entry point: uv run python -m server → http://127.0.0.1:8765 (localhost only)."""

import os

import uvicorn

from server.app import create_app


def main() -> None:
    host = os.environ.get("WEBUI_HOST", "127.0.0.1")
    port = int(os.environ.get("WEBUI_PORT", "8765"))
    uvicorn.run(create_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
