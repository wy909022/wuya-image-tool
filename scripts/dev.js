// 启动脚本 — 清除 ELECTRON_RUN_AS_NODE 环境变量后启动开发服务器
// 这是因为系统设置了 ELECTRON_RUN_AS_NODE=1，会导致 Electron 以纯 Node.js 模式运行
const { spawn } = require('child_process');
const { join } = require('path');

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE; // 关键：清除此变量

const electronVite = join(__dirname, '..', 'node_modules', '.bin', 'electron-vite');
const child = spawn(electronVite + '.cmd', ['dev'], {
  env,
  stdio: 'inherit',
  shell: true
});

child.on('close', (code) => process.exit(code));
