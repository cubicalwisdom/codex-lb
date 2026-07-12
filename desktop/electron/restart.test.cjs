const assert = require("node:assert/strict");
const { EventEmitter } = require("node:events");
const test = require("node:test");

const { createPortableRestartCoordinator } = require("./restart.cjs");

function createChild({ exits = true } = {}) {
  const child = new EventEmitter();
  child.exitCode = null;
  child.killed = false;
  child.kill = () => {
    child.killed = true;
    if (exits) {
      queueMicrotask(() => {
        child.exitCode = 0;
        child.emit("exit", 0, null);
      });
    }
    return true;
  };
  return child;
}

function createHarness(options = {}) {
  const calls = [];
  const scheduled = [];
  const child = Object.hasOwn(options, "child") ? options.child : createChild();
  const app = {
    relaunch: () => calls.push("relaunch"),
    exit: (code) => calls.push(`exit:${code}`),
  };
  const restart = createPortableRestartCoordinator({
    app,
    getBackendProcess: () => child,
    markQuitting: () => calls.push("mark-quitting"),
    appendLog: (_root, message) => calls.push(`log:${message}`),
    root: "H:\\Portable",
    timeoutMs: options.timeoutMs ?? 25,
    scheduleExit: (callback) => scheduled.push(callback),
  });
  return { app, calls, child, restart, scheduled };
}

test("waits for the owned backend before scheduling a portable relaunch", async () => {
  const harness = createHarness();

  const result = await harness.restart();

  assert.deepEqual(result, { success: true, message: "Codex LB is restarting" });
  assert.equal(harness.child.killed, true);
  assert.ok(harness.calls.indexOf("mark-quitting") < harness.calls.indexOf("relaunch"));
  assert.equal(harness.scheduled.length, 1);
  assert.equal(harness.calls.includes("exit:0"), false);

  harness.scheduled[0]();
  assert.equal(harness.calls.at(-1), "exit:0");
});

test("refuses to restart when this Electron process does not own the backend", async () => {
  const harness = createHarness({ child: null });

  const result = await harness.restart();

  assert.deepEqual(result, {
    success: false,
    message: "Codex LB backend is not owned by this app",
  });
  assert.equal(harness.calls.includes("relaunch"), false);
  assert.equal(harness.scheduled.length, 0);
});

test("deduplicates concurrent restart requests", async () => {
  const harness = createHarness();

  const [first, second] = await Promise.all([harness.restart(), harness.restart()]);

  assert.deepEqual(first, second);
  assert.equal(harness.calls.filter((call) => call === "mark-quitting").length, 1);
  assert.equal(harness.calls.filter((call) => call === "relaunch").length, 1);
  assert.equal(harness.scheduled.length, 1);
});

test("does not relaunch when the owned backend misses the stop deadline", async () => {
  const harness = createHarness({ child: createChild({ exits: false }), timeoutMs: 5 });

  const result = await harness.restart();

  assert.deepEqual(result, {
    success: false,
    message: "Codex LB backend did not stop in time",
  });
  assert.equal(harness.calls.includes("relaunch"), false);
  assert.equal(harness.scheduled.length, 0);
});
