const { app, BrowserWindow, dialog, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const HOST = process.env.CODEX_IB_HOST || "127.0.0.1";
const PORT = Number.parseInt(process.env.CODEX_IB_PORT || "2455", 10);
const BASE_URL = `http://${HOST}:${PORT}`;
const CODEXNEO_URL = `${BASE_URL}/codexneo`;
const HEALTH_URL = `${BASE_URL}/health`;

let mainWindow = null;
let backendProcess = null;

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
  fs.appendFileSync(path.join(logDir, "codex-ib-electron.log"), line, "utf8");
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

  const stdout = fs.openSync(path.join(logDir, "codex-ib-server.out.log"), "a");
  const stderr = fs.openSync(path.join(logDir, "codex-ib-server.err.log"), "a");
  const env = {
    ...process.env,
    CODEX_LB_DATA_DIR: dataDir,
    PYTHONPATH: path.join(root, ".venv", "Lib", "site-packages"),
    PYTHONUTF8: "1",
    PYTHONIOENCODING: "utf-8",
    HOST,
    PORT: String(PORT),
  };

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
      sandbox: true,
    },
  });

  mainWindow.once("ready-to-show", () => {
    mainWindow.show();
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });

  mainWindow.webContents.on("did-fail-load", (_event, errorCode, errorDescription) => {
    appendLog(root, `Window failed to load ${CODEXNEO_URL}: ${errorCode} ${errorDescription}`);
  });

  mainWindow.loadURL(CODEXNEO_URL);
}

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

app.whenReady().then(boot);

app.on("activate", () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow(sidecarRoot());
  }
});

app.on("before-quit", () => {
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
