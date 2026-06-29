function claimPortableSingleInstance({ app, root, appendLog, showMainWindow }) {
  if (!app.requestSingleInstanceLock()) {
    appendLog(root, "Another Codex IB instance is already running; exiting this launcher.");
    app.quit();
    return false;
  }

  app.on("second-instance", () => {
    appendLog(root, "Second Codex IB launch detected; focusing existing window.");
    showMainWindow();
  });

  return true;
}

module.exports = { claimPortableSingleInstance };
