function applyStartWithWindowsSetting(electronApp, enabled) {
  const openAtLogin = Boolean(enabled);
  electronApp.setLoginItemSettings({
    openAtLogin,
    path: electronApp.getPath("exe"),
    args: [],
  });
  return openAtLogin;
}

module.exports = { applyStartWithWindowsSetting };
