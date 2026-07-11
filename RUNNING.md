# Running StudyGame

## First-time setup

```powershell
# 1. Python backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

# 2. Frontend deps
cd frontend
npm install
cd ..

# 3. Add your Gemini key (already done if backend\.env exists)
#    Copy backend\.env.example to backend\.env and paste your key.
```

## Start the app (one command)

```powershell
.\start.ps1
```

This builds the frontend and starts the server. Then open:

- **On this PC:** http://localhost:8000
- **On your iPad Air (same Wi-Fi):** http://192.168.100.194:8000
  *(that's this PC's current IP — it can change; `start.ps1` prints the live one)*

## iPad tips

- The iPad and PC must be on the **same Wi-Fi network**.
- If the iPad can't connect, allow the port through Windows Firewall once:
  ```powershell
  New-NetFirewallRule -DisplayName "StudyGame" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
  ```
- In Safari, tap **Share → Add to Home Screen** to get an app-like icon.

## Adding study materials

Either **drag files onto the Library page**, or drop `.docx / .pptx / .pdf / .txt`
files straight into the `StudyMaterials\` folder — the app watches it and imports
them automatically (even while running).

## Development mode (hot reload)

Run backend and frontend separately:

```powershell
# Terminal 1 — backend API
.\.venv\Scripts\python.exe -m uvicorn app.api.main:app --app-dir backend --reload --port 8000

# Terminal 2 — frontend with hot reload (proxies /api to :8000)
cd frontend
npm run dev        # http://localhost:5173
```

## Running tests

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest
```
