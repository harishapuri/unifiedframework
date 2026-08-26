"""CORS + static files so file:// demo pages can call the local HTTP gate."""

from __future__ import annotations

from pathlib import Path

STATIC_FILES = {"styles.css", "app.js", "index.html"}


def apply_cors(handler) -> None:
    handler.send_header("Access-Control-Allow-Origin", "*")
    handler.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
    handler.send_header("Access-Control-Allow-Headers", "*")


def send_options(handler) -> None:
    handler.send_response(204)
    apply_cors(handler)
    handler.end_headers()


def resolve_static(static_dir: Path, url_path: str) -> Path | None:
    if url_path in {"/", "/index.html"}:
        candidate = static_dir / "index.html"
        return candidate if candidate.is_file() else None
    name = url_path[len("/assets/") :] if url_path.startswith("/assets/") else url_path.lstrip("/")
    if "/" in name or name not in STATIC_FILES:
        return None
    candidate = static_dir / name
    return candidate if candidate.is_file() else None
