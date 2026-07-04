// 诊断脚本
console.log("=== Electron Diagnostic ===");
console.log("process.type:", process.type);
console.log("process.versions.electron:", process.versions.electron);

try {
  const resolved = require.resolve('electron');
  console.log("require.resolve('electron'):", resolved);
} catch (e) {
  console.log("require.resolve failed:", e.message);
}

const electron = require('electron');
console.log("typeof electron:", typeof electron);

if (typeof electron === 'string') {
  console.log("electron is PATH string:", electron);
  console.log("This is the BUG! Electron API not available.");
} else {
  console.log("electron keys:", Object.keys(electron).slice(0, 10));
}

// Check Node.js module patching
const Module = require('module');
console.log("Module._resolveFilename exists:", typeof Module._resolveFilename);
