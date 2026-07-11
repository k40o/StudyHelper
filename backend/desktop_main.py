"""Entry point for the desktop build: run directly for local testing, or
freeze with PyInstaller and let the Electron shell spawn it as a subprocess.

Electron sets STUDYGAME_DATA_DIR / STUDYGAME_MATERIALS_DIR / PORT before
launching so all state lives under the OS's per-user app-data folder instead
of next to the executable (which may be read-only once installed).
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("VECTOR_STORE", "simple")

if getattr(sys, "frozen", False):
    # PyInstaller --onedir layout: the built frontend is bundled as a sibling
    # "frontend" folder next to the executable.
    bundle_dir = os.path.dirname(sys.executable)
    os.environ.setdefault("STUDYGAME_FRONTEND_DIST", os.path.join(bundle_dir, "frontend"))


def main() -> None:
    import uvicorn

    from app.api.main import app

    port = int(os.environ.get("PORT", "8756"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
