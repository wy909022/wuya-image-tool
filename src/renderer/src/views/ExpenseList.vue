<template>
  <!-- 账单列表页面 — 按时间倒序展示所有支出记录 -->
  <div class="expense-list-page">
    <div class="page-header">
      <h2>📋 账单明细</h2>
      <p class="page-desc" v-if="totalExpense > 0">
        共 {{ expenses.length }} 笔，合计 <span class="total-amount">¥{{ totalExpense.toFixed(2) }}</span>
      </p>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-date-picker
        v-model="filterMonth"
        type="month"
        placeholder="选择月份"
        format="YYYY年MM月"
        value-format="YYYY-MM"
        clearable
        class="month-picker"
        @change="loadExpenses"
      />
      <el-select
        v-model="filterCategory"
        placeholder="全部分类"
        clearable
        class="category-select"
        @change="loadExpenses"
      >
        <el-option
          v-for="cat in categoriesL1"
          :key="cat.id"
          :label="cat.icon + ' ' + cat.name"
          :value="cat.name"
        />
      </el-select>
    </div>

    <!-- 空状态 -->
    <div v-if="expenses.length === 0" class="empty-state">
      <p class="empty-icon">📭</p>
      <p class="empty-text">暂无账单记录</p>
      <p class="empty-hint">去"记账"页面添加一笔吧</p>
    </div>

    <!-- 账单列表 -->
    <div v-else class="expense-list">
      <div v-for="group in groupedExpenses" :key="group.date" class="date-group">
        <div class="date-header">
          <span class="date-text">{{ group.displayDate }}</span>
          <span class="date-total">¥{{ group.dayTotal.toFixed(2) }}</span>
        </div>

        <div
          v-for="expense in group.items"
          :key="expense.id"
          class="expense-item"
          @click="confirmDelete(expense)"
        >
          <div class="item-left">
            <span class="item-icon">{{ getCategoryIcon(expense.category_l1) }}</span>
            <div class="item-info">
              <span class="item-category">{{ expense.category_l1 }} · {{ expense.category_l2 }}</span>
              <span v-if="expense.note" class="item-note">{{ expense.note }}</span>
            </div>
          </div>
          <span class="item-amount">-¥{{ expense.amount.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <el-dialog v-model="showDeleteDialog" title="确认删除" width="300px" :close-on-click-modal="false">
      <p style="text-align: center; color: #606266;">确定要删除这笔记录吗？</p>
      <p v-if="deletingExpense" style="text-align: center; font-size: 16px; font-weight: 600; color: #f56c6c;">
        -¥{{ deletingExpense.amount.toFixed(2) }}
      </p>
      <template #footer>
        <el-button @click="showDeleteDialog = false">取消</el-button>
        <el-button type="danger" @click="doDelete" :loading="deleting">确认删除</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import dayjs from 'dayjs'

const expenses = ref([])
const categoriesL1 = ref([])
const filterMonth = ref('')
const filterCategory = ref('')
const showDeleteDialog = ref(false)
const deletingExpense = ref(null)
const deleting = ref(false)

// 加载分类和账单
onMounted(async () => {
  try {
    categoriesL1.value = await window.electronAPI.getCategoriesL1()
  } catch (e) {
    console.error('加载分类失败:', e)
  }
  await loadExpenses()
})

// 加载支出列表
async function loadExpenses() {
  try {
    const filters = {}
    if (filterMonth.value) filters.month = filterMonth.value
    if (filterCategory.value) filters.category_l1 = filterCategory.value

    expenses.value = await window.electronAPI.getExpenses(filters)
  } catch (e) {
    ElMessage.error('加载账单失败：' + e)
  }
}

// 合计
const totalExpense = computed(() => {
  return expenses.value.reduce((sum, e) => sum + e.amount, 0)
})

// 按日期分组
const groupedExpenses = computed(() => {
  const groups = {}
  for (const expense of expenses.value) {
    if (!groups[expense.date]) {
      groups[expense.date] = { date: expense.date, items: [], dayTotal: 0 }
    }
    groups[expense.date].items.push(expense)
    groups[expense.date].dayTotal += expense.amount
  }

  return Object.values(groups).map(g => ({
    ...g,
    displayDate: formatDisplayDate(g.date)
  }))
})

// 格式化日期显示
function formatDisplayDate(dateStr) {
  const today = dayjs().format('YYYY-MM-DD')
  const yesterday = dayjs().subtract(1, 'day').format('YYYY-MM-DD')

  if (dateStr === today) return '今天'
  if (dateStr === yesterday) return '昨天'
  return dayjs(dateStr).format('M月D日 周dd')
}

// 获取分类图标
function getCategoryIcon(categoryName) {
  const cat = categoriesL1.value.find(c => c.name === categoryName)
  return cat ? cat.icon : '📌'
}

// 确认删除
function confirmDelete(expense) {
  deletingExpense.value = expense
  showDeleteDialog.value = true
}

// 执行删除
async function doDelete() {
  if (!deletingExpense.value) return
  deleting.value = true

  try {
    await window.electronAPI.deleteExpense(deletingExpense.value.id)
    ElMessage.success('已删除')
    showDeleteDialog.value = false
    deletingExpense.value = null
    await loadExpenses()
  } catch (e) {
    ElMessage.error('删除失败')
  } finally {
    deleting.value = false
  }
}
</script>

<style scoped>
.expense-list-page {
  padding: 16px;
}

.page-header {
  text-align: center;
  margin-bottom: 16px;
}

.page-header h2 {
  margin: 0;
  font-size: 22px;
  color: #303133;
}

.page-desc {
  margin: 4px 0 0;
  font-size: 13px;
  color: #909399;
}

.total-amount {
  color: #f56c6c;
  font-weight: 600;
  font-size: 15px;
}

.filter-bar {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.month-picker {
  flex: 1;
}

.category-select {
  flex: 1;
}

.empty-state {
  text-align: center;
  padding: 60px 20px;
}

.empty-icon {
  font-size: 48px;
  margin: 0 0 12px;
}

.empty-text {
  font-size: 16px;
  color: #909399;
  margin: 0;
}

.empty-hint {
  font-size: 13px;
  color: #c0c4cc;
  margin: 4px 0 0;
}

.expense-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.date-group {
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
}

.date-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: #fafbfc;
  border-bottom: 1px solid #f0f0f0;
}

.date-text {
  font-size: 13px;
  font-weight: 500;
  color: #606266;
}

.date-total {
  font-size: 13px;
  color: #f56c6c;
  font-weight: 500;
}

.expense-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.expense-item:not(:last-child) {
  border-bottom: 1px solid #f5f5f5;
}

.expense-item:hover {
  background: #fafbfc;
}

.item-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.item-icon {
  font-size: 24px;
  width: 36px;
  text-align: center;
}

.item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.item-category {
  font-size: 14px;
  color: #303133;
}

.item-note {
  font-size: 12px;
  color: #909399;
}

.item-amount {
  font-size: 16px;
  font-weight: 600;
  color: #f56c6c;
  white-space: nowrap;
}
</style>
