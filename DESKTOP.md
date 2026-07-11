# Study Helper — desktop app (Windows / Mac / Linux)

The desktop app is an Electron window that spawns the real Python backend as a
local subprocess (bundled by PyInstaller — no Python install required by the
end user) and opens `http://127.0.0.1:8756` in a native window. Each account's
data lives in the OS's per-user app-data folder, so it's untouched by
reinstalls/updates:

| OS | Data location |
|----|----|
| Windows | `%APPDATA%\study-helper-desktop\` |
| macOS | `~/Library/Application Support/study-helper-desktop/` |
| Linux | `~/.config/study-helper-desktop/` |

## Try it locally (dev mode, current OS only)
No build needed — Electron spawns the backend straight from source using this
repo's `.venv`:
```bash
cd electron
npm install
npm start
```

## Build a real installer
PyInstaller and Electron both produce **native** binaries for whatever OS they
run on — there's no cross-compiling a Windows `.exe` from a Mac, etc. Two ways
to get all three platforms:

### Option A — GitHub Actions (recommended, builds all 3 at once)
This repo includes [`.github/workflows/build-desktop.yml`](.github/workflows/build-desktop.yml),
which builds on `windows-latest` + `macos-latest` + `ubuntu-latest` in parallel
and uploads each installer as a workflow artifact.

1. Push this repo to GitHub (see [DEPLOY.md](DEPLOY.md) for the git/GitHub steps).
2. On GitHub: **Actions** tab → **Build desktop app** → **Run workflow**.
3. When it finishes, download the three `study-helper-<os>` artifacts — each
   contains the installer for that platform (`.exe`, `.dmg`, `.AppImage`).

### Option B — Build locally (only produces an installer for *this* machine's OS)
```bash
# 1. Freeze the backend (from backend/)
pip install -r requirements-deploy.txt pyinstaller
pyinstaller --name studygame-backend --onedir --noconfirm --clean \
  --hidden-import uvicorn.loops.auto --hidden-import uvicorn.protocols.http.auto \
  --hidden-import uvicorn.protocols.websockets.auto --hidden-import uvicorn.lifespan.on \
  --collect-all pptx --collect-all docx --collect-all fitz \
  desktop_main.py

# 2. Build the frontend (from frontend/)
npm ci && npm run build

# 3. Assemble + package (from repo root)
mkdir -p electron/resources/backend electron/resources/frontend
cp -r backend/dist/studygame-backend/* electron/resources/backend/
cp -r frontend/dist/* electron/resources/frontend/
cd electron && npm install && npx electron-builder
```
The installer lands in `electron/release/`.

## Notes
- The bundled backend uses the lightweight NumPy vector store (no ChromaDB),
  keeping the frozen executable small — same as the cloud deploy.
- Auto-import from a watched folder only works once there's exactly one
  account on that machine (ownership would be ambiguous with several) — drag
  files into the **Library** tab instead, which always works.
- `electron/resources/` is gitignored — it's assembled at build time, not committed.
