"""Locate the unified framework: env, sibling checkout, then vendored copy."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _candidates() -> list[Path]:
    env = os.environ.get("UNIFIED_FRAMEWORK")
    paths: list[Path] = []
    if env:
        paths.append(Path(env).expanduser().resolve())
    paths.append(ROOT.parent / "unified_framework")
    paths.append(ROOT / "vendor" / "unified_framework")
    return paths


def locate() -> Path:
    try:
        import framework as _fw

        root = Path(_fw.__file__).resolve().parent.parent
        resolved = str(root)
        if resolved not in sys.path:
            sys.path.insert(0, resolved)
        return root
    except ImportError:
        pass
    for path in _candidates():
        if (path / "framework" / "__init__.py").is_file():
            resolved = str(path)
            if resolved not in sys.path:
                sys.path.insert(0, resolved)
            return path
    raise RuntimeError(
        "unified_framework not found. Set UNIFIED_FRAMEWORK or keep "
        "vendor/unified_framework in this repo."
    )


UNIFIED_ROOT = locate()
