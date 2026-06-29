const assert = require("node:assert/strict");
const test = require("node:test");

const { claimPortableSingleInstance } = require("./single-instance.cjs");

test("claimPortableSingleInstance quits the second launcher process", () => {
  const calls = [];
  const fakeApp = {
    requestSingleInstanceLock() {
      calls.push("request-lock");
      return false;
    },
    quit() {
      calls.push("quit");
    },
    on() {
      calls.push("on");
    },
  };

  const claimed = claimPortableSingleInstance({
    app: fakeApp,
    root: "H:\\Portable",
    appendLog: (_root, message) => calls.push(`log:${message}`),
    showMainWindow: () => calls.push("show"),
  });

  assert.equal(claimed, false);
  assert.deepEqual(calls, [
    "request-lock",
    "log:Another Codex IB instance is already running; exiting this launcher.",
    "quit",
  ]);
});

test("claimPortableSingleInstance focuses the existing window for later launches", () => {
  const calls = [];
  const fakeApp = {
    requestSingleInstanceLock() {
      calls.push("request-lock");
      return true;
    },
    quit() {
      calls.push("quit");
    },
    on(event, handler) {
      calls.push(`on:${event}`);
      if (event === "second-instance") handler();
    },
  };

  const claimed = claimPortableSingleInstance({
    app: fakeApp,
    root: "H:\\Portable",
    appendLog: (_root, message) => calls.push(`log:${message}`),
    showMainWindow: () => calls.push("show"),
  });

  assert.equal(claimed, true);
  assert.deepEqual(calls, [
    "request-lock",
    "on:second-instance",
    "log:Second Codex IB launch detected; focusing existing window.",
    "show",
  ]);
});
