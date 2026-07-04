// Electron 主进程 — 负责创建窗口和管理应用生命周期
import { app, BrowserWindow, ipcMain } from 'electron'
import { join } from 'path'
// 使用 sql-wasm 版本（WASM 内嵌在 JS 中，无需单独加载文件）
import initSqlJs from 'sql.js/dist/sql-wasm.js'
import fs from 'fs'
import path from 'path'

let mainWindow = null
let db = null
let dbPath = ''

// ====== 数据库工具函数 ======

// 执行查询并将结果转为对象数组（sql.js exec 返回 {columns, values} 格式）
function queryAll(sql, params = []) {
  const stmt = db.prepare(sql)
  if (params.length > 0) stmt.bind(params)
  const rows = []
  while (stmt.step()) {
    rows.push(stmt.getAsObject())
  }
  stmt.free()
  return rows
}

// 执行单条查询
function queryOne(sql, params = []) {
  const rows = queryAll(sql, params)
  return rows.length > 0 ? rows[0] : null
}

// 保存数据库到磁盘文件
function saveDatabase() {
  try {
    const data = db.export()
    const buffer = Buffer.from(data)
    fs.writeFileSync(dbPath, buffer)
  } catch (e) {
    console.error('保存数据库失败:', e)
  }
}

// 初始化数据库
async function initDatabase() {
  // 数据库文件存储在用户数据目录
  dbPath = path.join(app.getPath('userData'), 'wuya-accounting.db')

  // 初始化 sql.js（加载 WASM）
  const SQL = await initSqlJs()

  // 如果已有数据库文件则加载，否则创建新的
  if (fs.existsSync(dbPath)) {
    const fileBuffer = fs.readFileSync(dbPath)
    db = new SQL.Database(fileBuffer)
  } else {
    db = new SQL.Database()
  }

  // 创建支出记录表
  db.run(`
    CREATE TABLE IF NOT EXISTS expenses (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      amount REAL NOT NULL,
      category_l1 TEXT NOT NULL,
      category_l2 TEXT NOT NULL,
      date TEXT NOT NULL,
      note TEXT DEFAULT '',
      created_at TEXT DEFAULT (datetime('now', 'localtime'))
    )
  `)

  // 创建分类表
  db.run(`
    CREATE TABLE IF NOT EXISTS categories (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      parent_id INTEGER DEFAULT NULL,
      icon TEXT DEFAULT '',
      sort_order INTEGER DEFAULT 0
    )
  `)

  saveDatabase()
}

// 初始化默认分类数据
function initCategories() {
  const count = queryOne('SELECT COUNT(*) as count FROM categories')
  if (count && count.count > 0) return // 已有数据，跳过

  const categories = [
    { name: '餐饮饮食', parent: null, icon: '🍜', children: ['早餐', '午餐', '晚餐', '零食饮料', '聚餐请客', '外卖'] },
    { name: '交通出行', parent: null, icon: '🚗', children: ['公交地铁', '出租车/网约车', '加油充电', '停车费', '火车高铁', '飞机'] },
    { name: '购物消费', parent: null, icon: '🛒', children: ['日用百货', '服装鞋帽', '数码电子', '家居家具', '美妆护肤', '烟酒'] },
    { name: '居家住房', parent: null, icon: '🏠', children: ['房租', '水电燃气', '物业费', '维修保养', '宽带网费'] },
    { name: '休闲娱乐', parent: null, icon: '🎮', children: ['电影演出', '游戏充值', '体育运动', '旅游度假', 'KTV酒吧'] },
    { name: '医疗健康', parent: null, icon: '💊', children: ['看病挂号', '买药', '体检', '牙科眼科', '保健品'] },
    { name: '教育学习', parent: null, icon: '📚', children: ['书籍', '课程培训', '文具用品', '考试报名'] },
    { name: '人情往来', parent: null, icon: '🎁', children: ['红包礼金', '请客送礼', '孝敬父母', '结婚生子'] },
    { name: '通讯物流', parent: null, icon: '📱', children: ['手机话费', '快递邮寄'] },
    { name: '金融保险', parent: null, icon: '💰', children: ['手续费', '保险费', '理财亏损', '贷款利息'] },
    { name: '其他支出', parent: null, icon: '📌', children: ['其他'] }
  ]

  let order = 0

  for (const cat of categories) {
    db.run('INSERT INTO categories (name, parent_id, icon, sort_order) VALUES (?, ?, ?, ?)',
      [cat.name, null, cat.icon, order++])
    const result = queryOne('SELECT last_insert_rowid() as id')
    const parentId = result.id

    for (const child of cat.children) {
      db.run('INSERT INTO categories (name, parent_id, icon, sort_order) VALUES (?, ?, ?, ?)',
        [child, parentId, '', order++])
    }
  }

  saveDatabase()
}

// 创建主窗口
function createWindow() {
  mainWindow = new BrowserWindow({
    width: 430,
    height: 750,
    minWidth: 380,
    minHeight: 600,
    show: false,
    title: '无涯记账',
    autoHideMenuBar: true,
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      contextIsolation: true,
      nodeIntegration: false
    }
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow.show()
  })

  // 有 ELECTRON_RENDERER_URL 环境变量 → 开发模式
  // 没有 → 生产模式，加载打包后的 HTML
  if (process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }
}

// ====== IPC 通信处理（渲染进程 ↔ 主进程） ======

// 获取所有一级分类
ipcMain.handle('get-categories-l1', () => {
  return queryAll('SELECT * FROM categories WHERE parent_id IS NULL ORDER BY sort_order')
})

// 根据一级分类ID获取二级分类
ipcMain.handle('get-categories-l2', (_event, parentId) => {
  return queryAll('SELECT * FROM categories WHERE parent_id = ? ORDER BY sort_order', [parentId])
})

// 添加支出记录
ipcMain.handle('add-expense', (_event, expense) => {
  const { amount, category_l1, category_l2, date, note } = expense
  db.run(
    'INSERT INTO expenses (amount, category_l1, category_l2, date, note) VALUES (?, ?, ?, ?, ?)',
    [amount, category_l1, category_l2, date, note || '']
  )
  saveDatabase()
  return { success: true }
})

// 获取支出记录列表
ipcMain.handle('get-expenses', (_event, filters = {}) => {
  let sql = 'SELECT * FROM expenses WHERE 1=1'
  const params = []

  if (filters.month) {
    sql += " AND strftime('%Y-%m', date) = ?"
    params.push(filters.month)
  }

  if (filters.category_l1) {
    sql += ' AND category_l1 = ?'
    params.push(filters.category_l1)
  }

  sql += ' ORDER BY date DESC, created_at DESC'

  if (filters.limit) {
    sql += ' LIMIT ?'
    params.push(filters.limit)
  }
  if (filters.offset) {
    sql += ' OFFSET ?'
    params.push(filters.offset)
  }

  return queryAll(sql, params)
})

// 删除支出记录
ipcMain.handle('delete-expense', (_event, id) => {
  db.run('DELETE FROM expenses WHERE id = ?', [id])
  saveDatabase()
  return { success: true }
})

// 获取月度支出统计
ipcMain.handle('get-monthly-stats', () => {
  return queryAll(`
    SELECT strftime('%Y-%m', date) as month,
           SUM(amount) as total,
           COUNT(*) as count
    FROM expenses
    GROUP BY month
    ORDER BY month DESC
  `)
})

// 获取分类支出统计（指定月份）
ipcMain.handle('get-category-stats', (_event, month) => {
  let sql = `
    SELECT category_l1, SUM(amount) as total, COUNT(*) as count
    FROM expenses
  `
  const params = []
  if (month) {
    sql += " WHERE strftime('%Y-%m', date) = ?"
    params.push(month)
  }
  sql += ' GROUP BY category_l1 ORDER BY total DESC'

  return queryAll(sql, params)
})

// 应用启动
app.whenReady().then(async () => {
  // 设置 Windows 任务栏用户模型ID
  if (process.platform === 'win32') {
    app.setAppUserModelId('com.wuya.accounting')
  }

  // 初始化数据库
  await initDatabase()
  initCategories()

  // 创建主窗口
  createWindow()

  // macOS 点击 dock 图标重新创建窗口
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

// 所有窗口关闭时退出应用（macOS 除外）
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

// 应用退出前关闭数据库
app.on('will-quit', () => {
  if (db) {
    db.close()
    db = null
  }
})
