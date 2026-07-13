"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { rotateLogFile } = require("./log-rotation.cjs");

test("rotates oversized logs and keeps the configured backup count", (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "codex-lb-log-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const logPath = path.join(directory, "server.log");
  fs.writeFileSync(logPath, "current");
  fs.writeFileSync(`${logPath}.1`, "prior");
  fs.writeFileSync(`${logPath}.2`, "oldest");

  assert.equal(rotateLogFile(fs, logPath, { maxBytes: 1, backupCount: 2 }), true);
  assert.equal(fs.readFileSync(`${logPath}.1`, "utf8"), "current");
  assert.equal(fs.readFileSync(`${logPath}.2`, "utf8"), "prior");
  assert.equal(fs.existsSync(logPath), false);
});

test("leaves a log below the size threshold untouched", (t) => {
  const directory = fs.mkdtempSync(path.join(os.tmpdir(), "codex-lb-log-"));
  t.after(() => fs.rmSync(directory, { recursive: true, force: true }));
  const logPath = path.join(directory, "server.log");
  fs.writeFileSync(logPath, "small");
  assert.equal(rotateLogFile(fs, logPath, { maxBytes: 100, backupCount: 2 }), false);
  assert.equal(fs.readFileSync(logPath, "utf8"), "small");
});
