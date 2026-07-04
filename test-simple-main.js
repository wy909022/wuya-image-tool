console.log("=== AFTER UNSET ELECTRON_RUN_AS_NODE ===");
console.log("ELECTRON_RUN_AS_NODE:", process.env.ELECTRON_RUN_AS_NODE || "unset");
console.log("process.type:", process.type);
const e = require('electron');
console.log("typeof electron:", typeof e);
if (typeof e === 'object') {
  console.log("SUCCESS! has app:", typeof e.app, "has BrowserWindow:", typeof e.BrowserWindow);
  e.app.whenReady().then(() => { console.log("APP READY!"); e.app.quit(); });
} else {
  console.log("FAIL: " + e);
}
