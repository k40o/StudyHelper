// Electron shell: spawns the bundled Python backend as a child process, waits
// for it to report healthy, then opens a window pointed at it. In dev mode
// (no packaged backend present) it spawns the venv's python running
// desktop_main.py directly, so `npm start` works without a PyInstaller build.
const { app, BrowserWindow, Menu, shell, ipcMain } = require("electron");
const path = require("path");
const fs = require("fs");
const { spawn } = require("child_process");
const http = require("http");
const { loadSettings, saveSettings } = require("./settings");

const PORT = 8756;
const HEALTH_URL = `http://127.0.0.1:${PORT}/healthz`;
const APP_URL = `http://127.0.0.1:${PORT}/`;

let backendProcess = null;
let mainWindow = null;
let setupWindow = null;

function backendEnv() {
  const settings = loadSettings();
  return {
    ...process.env,
    PORT: String(PORT),
    VECTOR_STORE: "simple",
    STUDYGAME_DATA_DIR: path.join(app.getPath("userData"), "data"),
    STUDYGAME_MATERIALS_DIR: path.join(app.getPath("userData"), "StudyMaterials"),
    // Empty is fine — the backend just runs with AI features disabled, same
    // as the web app when no key is configured.
    GEMINI_API_KEY: settings.geminiApiKey || "",
  };
}

function startBackend() {
  const frozenExe = path.join(
    process.resourcesPath,
    "backend",
    process.platform === "win32" ? "studygame-backend.exe" : "studygame-backend"
  );

  if (fs.existsSync(frozenExe)) {
    backendProcess = spawn(frozenExe, [], { env: backendEnv() });
  } else {
    // Dev fallback: run straight from source with the repo's venv.
    const repoRoot = path.join(__dirname, "..");
    const venvPython =
      process.platform === "win32"
        ? path.join(repoRoot, ".venv", "Scripts", "python.exe")
        : path.join(repoRoot, ".venv", "bin", "python");
    const python = fs.existsSync(venvPython) ? venvPython : "python3";
    backendProcess = spawn(python, ["desktop_main.py"], {
      cwd: path.join(repoRoot, "backend"),
      env: backendEnv(),
    });
  }

  backendProcess.stdout?.on("data", (d) => console.log(`[backend] ${d}`.trimEnd()));
  backendProcess.stderr?.on("data", (d) => console.error(`[backend] ${d}`.trimEnd()));
  backendProcess.on("exit", (code) => console.log(`[backend] exited with code ${code}`));
}

function stopBackend() {
  if (backendProcess && !backendProcess.killed) backendProcess.kill();
  backendProcess = null;
}

function waitForBackend(retriesLeft = 60) {
  return new Promise((resolve, reject) => {
    const attempt = () => {
      http
        .get(HEALTH_URL, (res) => {
          if (res.statusCode === 200) resolve();
          else retry();
        })
        .on("error", retry);
    };
    const retry = () => {
      if (--retriesLeft <= 0) return reject(new Error("Backend did not become healthy in time"));
      setTimeout(attempt, 500);
    };
    attempt();
  });
}

// Shown once on first run (no Gemini key saved yet), and again any time the
// user picks Settings > Gemini API Key from the menu.
function showSetupWindow() {
  return new Promise((resolve) => {
    setupWindow = new BrowserWindow({
      width: 480,
      height: 480,
      resizable: false,
      icon: path.join(__dirname, "build", "icon.png"),
      backgroundColor: "#0d1020",
      webPreferences: {
        contextIsolation: true,
        nodeIntegration: false,
        preload: path.join(__dirname, "preload.js"),
      },
    });
    setupWindow.setMenu(null);
    setupWindow.loadFile(path.join(__dirname, "setup.html"));
    setupWindow.on("closed", () => {
      setupWindow = null;
      resolve();
    });
  });
}

function buildMenu() {
  const template = [
    {
      label: "Settings",
      submenu: [
        {
          label: "Gemini API Key…",
          click: async () => {
            await showSetupWindow();
            // Restart the backend so it picks up the (possibly new) key.
            stopBackend();
            startBackend();
            await waitForBackend();
            mainWindow?.loadURL(APP_URL);
          },
        },
      ],
    },
  ];
  Menu.setApplicationMenu(Menu.buildFromTemplate(template));
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1200,
    height: 860,
    minWidth: 720,
    minHeight: 560,
    icon: path.join(__dirname, "build", "icon.png"),
    backgroundColor: "#0d1020",
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  // Open any target="_blank" links in the OS browser instead of a new Electron window.
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  await waitForBackend();
  mainWindow.loadURL(APP_URL);
}

ipcMain.handle("settings:get", () => loadSettings());
ipcMain.handle("settings:save", (_event, partial) => saveSettings(partial));
ipcMain.handle("settings:open-external", (_event, url) => shell.openExternal(url));

app.whenReady().then(async () => {
  buildMenu();

  const settings = loadSettings();
  if (!settings.geminiApiKey) {
    await showSetupWindow();
  }

  startBackend();
  try {
    await createWindow();
  } catch (err) {
    console.error(err);
    app.quit();
  }

  app.on("activate", () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") app.quit();
});

app.on("before-quit", () => {
  stopBackend();
});
