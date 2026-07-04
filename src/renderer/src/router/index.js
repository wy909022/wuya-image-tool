// Vue Router 路由配置 — 定义页面导航
import { createRouter, createWebHashHistory } from 'vue-router'

const router = createRouter({
  history: createWebHashHistory(),
  routes: [
    {
      path: '/',
      redirect: '/add'
    },
    {
      path: '/add',
      name: 'add-expense',
      component: () => import('@/views/AddExpense.vue'),
      meta: { title: '记账' }
    },
    {
      path: '/list',
      name: 'expense-list',
      component: () => import('@/views/ExpenseList.vue'),
      meta: { title: '账单' }
    },
    {
      path: '/stats',
      name: 'stats',
      component: () => import('@/views/Stats.vue'),
      meta: { title: '统计' }
    }
  ]
})

export default router
