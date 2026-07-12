function waitForExit(child, timeoutMs) {
  return new Promise((resolve) => {
    let settled = false;
    const finish = (exited) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      child.removeListener("exit", onExit);
      resolve(exited);
    };
    const onExit = () => finish(true);
    const timeout = setTimeout(() => finish(false), timeoutMs);
    child.once("exit", onExit);
    if (!child.kill()) finish(false);
  });
}

async function restartOwnedBackendAndApp({
  app,
  backendProcess,
  markQuitting,
  appendLog,
  root,
  timeoutMs,
  scheduleExit,
}) {
  if (!backendProcess || backendProcess.exitCode !== null) {
    const message = "Codex LB backend is not owned by this app";
    appendLog(root, `Restart refused: ${message}.`);
    return { success: false, message };
  }

  appendLog(root, `Restart requested; stopping owned backend PID ${backendProcess.pid ?? "unknown"}.`);
  const exited = await waitForExit(backendProcess, timeoutMs);
  if (!exited) {
    const message = "Codex LB backend did not stop in time";
    appendLog(root, `Restart failed: ${message}.`);
    return { success: false, message };
  }

  markQuitting();
  app.relaunch();
  appendLog(root, "Owned backend stopped; portable relaunch scheduled.");
  scheduleExit(() => app.exit(0));
  return { success: true, message: "Codex LB is restarting" };
}

function createPortableRestartCoordinator({
  app,
  getBackendProcess,
  markQuitting,
  appendLog,
  root,
  timeoutMs = 5000,
  scheduleExit = setImmediate,
}) {
  let restartPromise = null;
  return async function restartPortableApp() {
    if (restartPromise) return restartPromise;
    restartPromise = restartOwnedBackendAndApp({
      app,
      backendProcess: getBackendProcess(),
      markQuitting,
      appendLog,
      root,
      timeoutMs,
      scheduleExit,
    });
    const result = await restartPromise;
    if (!result.success) restartPromise = null;
    return result;
  };
}

module.exports = { createPortableRestartCoordinator };
