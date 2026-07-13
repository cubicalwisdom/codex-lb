const { app, BrowserWindow, Menu, Tray, dialog, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");
const { claimPortableSingleInstance } = require("./single-instance.cjs");
const { applyStartWithWindowsSetting } = require("./startup.cjs");
const { createPortableRestartCoordinator } = require("./restart.cjs");
const { rotateLogFile } = require("./log-rotation.cjs");
const { assertTrustedIpcSender, isAllowedAppUrl, isSafeExternalUrl } = require("./security.cjs");

const HOST = process.env.CODEX_IB_HOST || "127.0.0.1";
const PORT = Number.parseInt(process.env.CODEX_IB_PORT || "2455", 10);
const BASE_URL = `http://${HOST}:${PORT}`;
const CODEXNEO_URL = `${BASE_URL}/codexneo`;
const HEALTH_URL = `${BASE_URL}/health`;
const LOG_MAX_BYTES = Number.parseInt(process.env.CODEX_IB_LOG_MAX_BYTES || String(10 * 1024 * 1024), 10);
const LOG_BACKUP_COUNT = Number.parseInt(process.env.CODEX_IB_LOG_BACKUP_COUNT || "5", 10);

let mainWindow = null;
let backendProcess = null;
let tray = null;
let isQuitting = false;
let minimizeToTrayEnabled = false;
let startWithWindowsEnabled = false;

function sidecarRoot() {
  if (app.isPackaged) {
    return path.dirname(app.getPath("exe"));
  }
  return process.env.CODEX_IB_PORTABLE_ROOT || path.resolve(__dirname, "..", "..");
}

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function appendLog(root, message) {
  const logDir = path.join(root, "logs");
  ensureDir(logDir);
  const line = `[${new Date().toISOString()}] ${message}\n`;
  const logPath = path.join(logDir, "codex-ib-electron.log");
  rotateLogFile(fs, logPath, { maxBytes: LOG_MAX_BYTES, backupCount: LOG_BACKUP_COUNT });
  fs.appendFileSync(logPath, line, "utf8");
}

function iconPath() {
  return path.join(__dirname, "assets", "icon.ico");
}

function showMainWindow() {
  if (!mainWindow) {
    createWindow(sidecarRoot());
    return;
  }
  mainWindow.show();
  if (mainWindow.isMinimized()) {
    mainWindow.restore();
  }
  mainWindow.focus();
}

function ensureTray(root) {
  if (tray) return tray;
  tray = new Tray(iconPath());
  tray.setToolTip("Codex IB");
  tray.setContextMenu(
    Menu.buildFromTemplate([
      { label: "Show Codex IB", click: showMainWindow },
      {
        label: "Quit",
        click: () => {
          isQuitting = true;
          appendLog(root, "Quit selected from tray.");
          app.quit();
        },
      },
    ]),
  );
  tray.on("click", showMainWindow);
  appendLog(root, "Tray icon created.");
  return tray;
}

function destroyTray(root) {
  if (!tray) return;
  tray.destroy();
  tray = null;
  appendLog(root, "Tray icon removed.");
}

async function healthOk() {
  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 2000);
    const response = await fetch(HEALTH_URL, { signal: controller.signal });
    clearTimeout(timeout);
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForHealth(root) {
  for (let attempt = 1; attempt <= 80; attempt += 1) {
    if (await healthOk()) {
      appendLog(root, `Codex IB became healthy after ${attempt} attempt(s).`);
      return true;
    }
    await new Promise((resolve) => setTimeout(resolve, 500));
  }
  return false;
}

function startBackend(root) {
  const bundledPythonExe = path.join(root, ".python", "python.exe");
  const venvPythonExe = path.join(root, ".venv", "Scripts", "python.exe");
  const pythonExe = fs.existsSync(bundledPythonExe) ? bundledPythonExe : venvPythonExe;
  if (!fs.existsSync(pythonExe)) {
    throw new Error(`Portable Python runtime not found: ${bundledPythonExe} or ${venvPythonExe}`);
  }

  const logDir = path.join(root, "logs");
  const dataDir = path.join(root, "portable-data");
  ensureDir(logDir);
  ensureDir(dataDir);

  const stdoutPath = path.join(logDir, "codex-ib-server.out.log");
  const stderrPath = path.join(logDir, "codex-ib-server.err.log");
  rotateLogFile(fs, stdoutPath, { maxBytes: LOG_MAX_BYTES, backupCount: LOG_BACKUP_COUNT });
  rotateLogFile(fs, stderrPath, { maxBytes: LOG_MAX_BYTES, backupCount: LOG_BACKUP_COUNT });
  const stdout = fs.openSync(stdoutPath, "a");
  const stderr = fs.openSync(stderrPath, "a");
  const env = {
    ...process.env,
    CODEX_LB_DATA_DIR: dataDir,
    CODEX_LB_BOOTSTRAP_TOKEN_FILE: path.join(dataDir, "dashboard-bootstrap-token.txt"),
    PYTHONPATH: path.join(root, ".venv", "Lib", "site-packages"),
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    HOST,
    PORT: String(PORT),
  };

  try {
    backendProcess = spawn(
      pythonExe,
      ["-m", "uvicorn", "app.main:app", "--host", HOST, "--port", String(PORT)],
      {
        cwd: root,
        env,
        windowsHide: true,
        stdio: ["ignore", stdout, stderr],
      },
    );
  } finally {
    fs.closeSync(stdout);
    fs.closeSync(stderr);
  }

  backendProcess.once("exit", (code, signal) => {
    appendLog(root, `Backend exited with code=${code ?? ""} signal=${signal ?? ""}.`);
    backendProcess = null;
  });

  backendProcess.once("error", (error) => {
    appendLog(root, `Backend failed to start: ${error.message}`);
  });

  appendLog(root, `Started backend PID ${backendProcess.pid}.`);
}

function createWindow(root) {
  mainWindow = new BrowserWindow({
    width: 1440,
    height: 920,
    minWidth: 1100,
    minHeight: 720,
    backgroundColor: "#050505",
    show: false,
    autoHideMenuBar: true,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      preload: path.join(__dirname, "preload.cjs"),
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.webContents.on("will-navigate", (event, url) => {
    if (!isAllowedAppUrl(url, BASE_URL)) {
      event.preventDefault();
      appendLog(root, `Blocked renderer navigation outside the app origin: ${url}`);
    }
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    if (isSafeExternalUrl(url)) {
      shell.openExternal(url).catch((error) => appendLog(root, `Failed to open external URL: ${error.message}`));
    } else {
      appendLog(root, `Blocked unsafe external URL: ${url}`);
    }
    return { action: "deny" };
  });

  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription) => {
    appendLog(root, `Window failed to load ${CODEXNEO_URL}: ${errorCode} ${errorDescription}`);
  });

  mainWindow.on("close", (event) => {
    if (!minimizeToTrayEnabled || isQuitting) return;
    event.preventDefault();
    ensureTray(root);
    mainWindow.hide();
    appendLog(root, "Window close hidden to tray because minimize-to-tray is enabled.");
  });

  mainWindow.loadURL(CODEXNEO_URL);
}

ipcMain.handle("codex-ib:set-minimize-to-tray-enabled", (event, enabled) => {
  assertTrustedIpcSender(event, BASE_URL);
  minimizeToTrayEnabled = Boolean(enabled);
  if (minimizeToTrayEnabled) {
    ensureTray(sidecarRoot());
  } else {
    destroyTray(sidecarRoot());
  }
  appendLog(sidecarRoot(), `Minimize-to-tray preference set to ${minimizeToTrayEnabled}.`);
  return minimizeToTrayEnabled;
});

ipcMain.handle("codex-ib:minimize", (event, options = {}) => {
  assertTrustedIpcSender(event, BASE_URL);
  if (!mainWindow) return false;
  const toTray = Boolean(options.toTray);
  minimizeToTrayEnabled = toTray;
  if (toTray) {
    ensureTray(sidecarRoot());
    mainWindow.hide();
    appendLog(sidecarRoot(), "Window minimized to tray.");
    return true;
  }
  destroyTray(sidecarRoot());
  mainWindow.minimize();
  appendLog(sidecarRoot(), "Window minimized normally.");
  return true;
});

ipcMain.handle("codex-ib:set-start-with-windows-enabled", (event, enabled) => {
  assertTrustedIpcSender(event, BASE_URL);
  startWithWindowsEnabled = applyStartWithWindowsSetting(app, enabled);
  appendLog(sidecarRoot(), `Start-with-Windows preference set to ${startWithWindowsEnabled}.`);
  return startWithWindowsEnabled;
});

const restartPortableApp = createPortableRestartCoordinator({
  app,
  getBackendProcess: () => backendProcess,
  markQuitting: () => {
    isQuitting = true;
  },
  appendLog,
  root: sidecarRoot(),
});

ipcMain.handle("codex-ib:restart", (event) => {
  assertTrustedIpcSender(event, BASE_URL);
  return restartPortableApp();
});

async function boot() {
  const root = sidecarRoot();
  appendLog(root, `Electron portable root: ${root}`);
  appendLog(root, `Codex IB URL: ${CODEXNEO_URL}`);

  if (!(await healthOk())) {
    startBackend(root);
    const ready = await waitForHealth(root);
    if (!ready) {
      const message = `Codex IB did not become healthy on ${HEALTH_URL}. Check ${path.join(root, "logs")}.`;
      appendLog(root, `ERROR: ${message}`);
      dialog.showErrorBox("Codex IB failed to start", message);
      app.quit();
      return;
    }
  } else {
    appendLog(root, `Reusing healthy Codex IB server on ${HEALTH_URL}.`);
  }

  createWindow(root);
}

if (claimPortableSingleInstance({ app, root: sidecarRoot(), appendLog, showMainWindow })) {
  app.whenReady().then(boot);
}

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow(sidecarRoot());
  }
});

app.on("before-quit", () => {
  isQuitting = true;
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
