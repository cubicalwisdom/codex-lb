"use strict";

function rotateLogFile(fs, logPath, { maxBytes = 10 * 1024 * 1024, backupCount = 5 } = {}) {
  if (!fs.existsSync(logPath) || fs.statSync(logPath).size < maxBytes) return false;
  if (backupCount < 1) {
    fs.truncateSync(logPath, 0);
    return true;
  }
  const oldest = `${logPath}.${backupCount}`;
  if (fs.existsSync(oldest)) fs.rmSync(oldest, { force: true });
  for (let index = backupCount - 1; index >= 1; index -= 1) {
    const source = `${logPath}.${index}`;
    if (fs.existsSync(source)) fs.renameSync(source, `${logPath}.${index + 1}`);
  }
  fs.renameSync(logPath, `${logPath}.1`);
  return true;
}

module.exports = { rotateLogFile };
