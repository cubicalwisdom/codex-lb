const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("codexIbElectron", {
  minimizeToTray: (options) => ipcRenderer.invoke("codex-ib:minimize", options),
  setMinimizeToTrayEnabled: (enabled) => ipcRenderer.invoke("codex-ib:set-minimize-to-tray-enabled", Boolean(enabled)),
  setStartWithWindowsEnabled: (enabled) =>
    ipcRenderer.invoke("codex-ib:set-start-with-windows-enabled", Boolean(enabled)),
  restartApp: () => ipcRenderer.invoke("codex-ib:restart"),
});
