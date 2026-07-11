# Study Helper — AI-Powered Study RPG

Turn your study materials (Word, PowerPoint, PDF, text) into an interactive
RPG that helps you learn, using AI + spaced repetition.

**Run locally:** [RUNNING.md](RUNNING.md) · **Deploy live (no PC needed):** [DEPLOY.md](DEPLOY.md)

- **Frontend:** React + Vite + TypeScript (runs in a browser and on iPad Safari;
  wrapped in Electron later for a desktop installer)
- **Backend:** Python + FastAPI
- **Database:** SQLite (game state) + ChromaDB (RAG embeddings)
- **AI:** Google Gemini (free tier), with an `AIProvider` abstraction so Ollama
  can be swapped in later

## Architecture (clean / layered)

```
backend/app/
  domain/          Pure business models & rules (no I/O) — e.g. document model
  application/     Services / use-cases (orchestration)
  infrastructure/  Adapters to the outside world:
    parsing/       docx · pptx · pdf · txt  ✅ Module 1
    ai/            Gemini provider + RAG            (planned)
    vectorstore/   ChromaDB embeddings              (planned)
    persistence/   SQLite + SQLAlchemy repositories (planned)
    watcher/       watchdog folder auto-detection   (planned)
  core/            config, logging
  api/             FastAPI routes                    (planned)
```

## Build progress

| # | Module | Status |
|---|--------|--------|
| 1 | Document parsing (docx/pptx/pdf/txt → normalized model) | ✅ Done, tested (7 tests) |
| 2 | Folder watcher + knowledge base (SQLite, auto-import) | ✅ Done, tested (7 tests) |
| 3 | AI layer: Gemini provider + RAG (ChromaDB) + Tutor | ✅ Done, tested (6 tests + live) |
| — | **Vertical slice**: FastAPI + React UI (upload, tutor, search), runs on PC + iPad | ✅ Done, live |
| 4 | Question generator (all 10 types) + Quiz UI | ✅ Done, tested (5 tests + live) |
| 5 | Game layer: XP, levels, coins, hearts, streaks, spaced repetition, achievements, dashboard | ✅ Done, tested (11 tests + live) |
| 6 | Boss battles (combo damage, victory bonuses, trophies) | ✅ Done, tested (6 tests + live) |
| — | Database + REST API — expanded incrementally each module | ✅ Ongoing |
| — | React game UI + dashboard — Claymorphism design system applied | ✅ Done |
| next | Electron desktop packaging + more game flavor (NPC teacher, collectibles) | ⬜ |

**Run it:** see [RUNNING.md](RUNNING.md) — `./start.ps1` then open http://localhost:8000.

## Getting started (backend)

```bash
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r backend/requirements.txt   # Windows
cd backend && ../.venv/Scripts/python.exe -m pytest                    # run tests
```

## Study materials

Drop your `.docx`, `.pptx`, `.pdf`, `.txt` files into `StudyMaterials/`.
