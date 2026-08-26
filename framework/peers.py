"""Start sibling plane demos — one project per site URL."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path

# One project, one site URL (same loopback, different ports).
PLANE_DEMOS = (
    ("CICD", "cicd.demo", 8871, "127.0.0.1"),
    ("infra", "infra.demo", 8872, "127.0.0.1"),
    ("zeroguard", "zeroguard.demo", 8873, "127.0.0.1"),
    ("maws", "maws.demo", 8874, "127.0.0.1"),
    ("unified_framework", "framework.webdemo", 8877, "127.0.0.1"),
)

PAGE_URLS = tuple(f"http://{host}:{port}/" for _folder, _mod, port, host in PLANE_DEMOS)

SITES = {
    "cicd": "http://127.0.0.1:8871/",
    "infra": "http://127.0.0.1:8872/",
    "zeroguard": "http://127.0.0.1:8873/",
    "maws": "http://127.0.0.1:8874/",
    "unified": "http://127.0.0.1:8877/",
}


def port_up(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.25)
        return sock.connect_ex((host, port)) == 0


def start_peer_demos(*, desktop: Path, self_port: int) -> list[str]:
    started: list[str] = []
    for folder, module, port, host in PLANE_DEMOS:
        if port == self_port or port_up(port, host):
            continue
        root = desktop / folder
        if module == "framework.webdemo":
            marker = root / "framework" / "webdemo.py"
        else:
            marker = root / module.split(".", 1)[0] / "demo.py"
        if not marker.is_file():
            continue
        subprocess.Popen(
            [sys.executable, "-m", module, "--no-browser", "--no-peers"],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        started.append(f"{folder} {host}:{port}")
    deadline = time.time() + 10
    for _folder, _module, port, host in PLANE_DEMOS:
        if port == self_port:
            continue
        while time.time() < deadline and not port_up(port, host):
            time.sleep(0.15)
    return started


def open_all_demo_pages() -> None:
    for url in PAGE_URLS:
        try:
            webbrowser.open_new_tab(url)
        except Exception:
            pass
        time.sleep(0.25)
