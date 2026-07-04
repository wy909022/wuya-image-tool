// 打包脚本 — 清除 ELECTRON_RUN_AS_NODE 后打包 Windows 安装程序
const { spawn } = require('child_process');
const { join } = require('path');

const env = { ...process.env };
delete env.ELECTRON_RUN_AS_NODE;

// 先构建
function runCommand(cmd, args, label) {
  return new Promise((resolve, reject) => {
    console.log(`\n>>> ${label}...\n`);
    const child = spawn(cmd, args, {
      env,
      stdio: 'inherit',
      shell: true
    });
    child.on('close', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${label} 失败，退出码: ${code}`));
    });
  });
}

(async () => {
  try {
    // 1. 构建前端
    const electronViteBin = join(__dirname, '..', 'node_modules', '.bin', 'electron-vite.cmd');
    await runCommand(electronViteBin, ['build'], '构建项目');

    // 2. 打包 Windows 安装程序
    const electronBuilderBin = join(__dirname, '..', 'node_modules', '.bin', 'electron-builder.cmd');
    await runCommand(electronBuilderBin, ['--win'], '打包 Windows 安装程序');

    console.log('\n✅ 打包完成！安装程序在 dist-electron/ 目录下');
  } catch (err) {
    console.error('\n❌', err.message);
    process.exit(1);
  }
})();
