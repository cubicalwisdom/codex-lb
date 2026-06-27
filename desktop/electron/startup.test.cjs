const assert = require("node:assert/strict");
const test = require("node:test");

const { applyStartWithWindowsSetting } = require("./startup.cjs");

test("applyStartWithWindowsSetting enables login startup for the packaged exe", () => {
  const calls = [];
  const fakeApp = {
    getPath(name) {
      assert.equal(name, "exe");
      return "H:\\Portable\\Codex IB.exe";
    },
    setLoginItemSettings(options) {
      calls.push(options);
    },
  };

  const enabled = applyStartWithWindowsSetting(fakeApp, true);

  assert.equal(enabled, true);
  assert.deepEqual(calls, [
    {
      openAtLogin: true,
      path: "H:\\Portable\\Codex IB.exe",
      args: [],
    },
  ]);
});

test("applyStartWithWindowsSetting disables login startup for the packaged exe", () => {
  const calls = [];
  const fakeApp = {
    getPath() {
      return "H:\\Portable\\Codex IB.exe";
    },
    setLoginItemSettings(options) {
      calls.push(options);
    },
  };

  const enabled = applyStartWithWindowsSetting(fakeApp, false);

  assert.equal(enabled, false);
  assert.deepEqual(calls, [
    {
      openAtLogin: false,
      path: "H:\\Portable\\Codex IB.exe",
      args: [],
    },
  ]);
});
