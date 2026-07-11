# Deploying Study Helper (run it live, no PC needed)

Once deployed, you get a permanent `https://...` URL that works on your iPad (and
your friends' devices) **from anywhere** — your PC does not need to be on, and you
never touch an IP address again. On the iPad you can **Add to Home Screen** to get
a real "Study Helper" app icon.

The app is packaged as a single Docker image (React frontend + Python API), using
the built-in lightweight vector store so it fits comfortably on small instances.

---

## What you need (one-time)
1. A **GitHub account** (free) — to hold the code the host builds from.
2. Your **Gemini API key** (you already have it). It is set as a secret in the host
   dashboard — never committed to the repo.

### Push the code to GitHub
```bash
cd studygame
git init
git add .
git commit -m "Study Helper"
# create an empty repo on github.com, then:
git remote add origin https://github.com/<you>/study-helper.git
git push -u origin main
```
> `.env` is git-ignored, so your key is **not** pushed.

---

## Option A — Render (easiest, ~$7/mo, reliable) ⭐ recommended
Render has a clean click-to-deploy flow and this repo includes a `render.yaml`.

1. Go to **https://render.com** → sign in with GitHub.
2. **New +** → **Blueprint** → pick your `study-helper` repo. Render reads
   `render.yaml` (a web service + a 1 GB persistent disk mounted at `/data`).
3. When prompted, set the **`GEMINI_API_KEY`** environment variable to your key.
4. Click **Apply**. First build takes a few minutes; then you get a URL like
   `https://study-helper.onrender.com`.

- The **`starter` plan (~$7/mo)** is set because it gives a **persistent disk** — your
  uploaded documents, questions, and game progress survive restarts/redeploys.
- To try it for free first, change `plan: starter` to `plan: free` in `render.yaml`.
  ⚠️ On free, the service sleeps when idle (slow first load) and **data resets on
  restart** — fine for a demo, not for real studying.

## Option B — Fly.io (genuinely free tier, a little more setup)
Fly gives a free allowance **and** free persistent volumes.

```bash
# install flyctl (https://fly.io/docs/hands-on/install-flyctl/), then:
fly launch --no-deploy          # detects the Dockerfile; pick a name/region
fly volume create data --size 1 # 1 GB persistent volume (free tier)
fly secrets set GEMINI_API_KEY=your-key-here
```
Then edit the generated `fly.toml` to mount the volume and expose the port:
```toml
[env]
  VECTOR_STORE = "simple"
  STUDYGAME_DATA_DIR = "/data"
  STUDYGAME_MATERIALS_DIR = "/data/StudyMaterials"

[[mounts]]
  source = "data"
  destination = "/data"

[http_service]
  internal_port = 8000
  force_https = true
```
Deploy: `fly deploy`. You'll get `https://<name>.fly.dev`.

---

## After it's live
- **On iPad:** open the URL in Safari → **Share → Add to Home Screen** → it installs
  as **Study Helper** with the book icon and opens full-screen like a native app.
- **Add study materials:** use the **Library** tab's upload (drag/drop or tap). In the
  cloud there's no watched folder — everything goes through the upload button.
- **Updating the app:** `git push` → Render/Fly auto-rebuilds and redeploys.

## Important notes
- **Accounts are required now.** Each person creates their own email/password
  account on first visit (a "Create account" tab on the login screen) and only
  ever sees their own documents, quizzes, and progress — safe to share the URL
  with friends. Anyone with the URL can still *sign up* and use your Gemini
  quota, so keep it semi-private if that matters.
- **Gemini free tier** has daily limits; heavy use across several friends may hit them.
- **Environment variables** the image understands:
  | Var | Purpose | Default |
  |-----|---------|---------|
  | `GEMINI_API_KEY` | your key (required) | — |
  | `VECTOR_STORE` | `simple` (lean) or `chroma` | `simple` in Docker |
  | `STUDYGAME_DATA_DIR` | where DB/vectors/uploads persist | `/data` |
  | `PORT` | injected by the host | `8000` |
