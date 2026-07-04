// 预加载脚本 — 在渲染进程和主进程之间建立安全的通信桥梁
import { contextBridge, ipcRenderer } from 'electron'

// 暴露安全的 API 给渲染进程（Vue 组件通过 window.electronAPI 调用）
contextBridge.exposeInMainWorld('electronAPI', {
  // 分类相关
  getCategoriesL1: () => ipcRenderer.invoke('get-categories-l1'),
  getCategoriesL2: (parentId) => ipcRenderer.invoke('get-categories-l2', parentId),

  // 支出记录相关
  addExpense: (expense) => ipcRenderer.invoke('add-expense', expense),
  getExpenses: (filters) => ipcRenderer.invoke('get-expenses', filters),
  deleteExpense: (id) => ipcRenderer.invoke('delete-expense', id),

  // 统计相关
  getMonthlyStats: () => ipcRenderer.invoke('get-monthly-stats'),
  getCategoryStats: (month) => ipcRenderer.invoke('get-category-stats', month)
})
