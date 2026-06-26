const { contextBridge, ipcRenderer } = require("electron");

contextBridge.exposeInMainWorld("codexIbElectron", {
  minimizeToTray: (options) => ipcRenderer.invoke("codex-ib:minimize", options),
  setMinimizeToTrayEnabled: (enabled) => ipcRenderer.invoke("codex-ib:set-minimize-to-tray-enabled", Boolean(enabled)),
});
