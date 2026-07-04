<template>
  <!-- 记账页面 — 添加支出记录 -->
  <div class="add-expense-page">
    <div class="page-header">
      <h2>✏️ 记一笔</h2>
      <p class="page-desc">记录你的每一笔支出</p>
    </div>

    <div class="form-card">
      <!-- 金额输入 -->
      <div class="form-group">
        <label class="form-label">金额（元）</label>
        <div class="amount-input-wrapper">
          <span class="currency-symbol">¥</span>
          <input
            v-model="form.amount"
            type="number"
            class="amount-input"
            placeholder="0.00"
            step="0.01"
            min="0.01"
            @input="validateAmount"
          />
        </div>
        <p v-if="amountError" class="error-text">{{ amountError }}</p>
      </div>

      <!-- 日期选择 -->
      <div class="form-group">
        <label class="form-label">日期</label>
        <el-date-picker
          v-model="form.date"
          type="date"
          placeholder="选择日期"
          format="YYYY/MM/DD"
          value-format="YYYY-MM-DD"
          class="full-width-input"
        />
      </div>

      <!-- 一级分类选择 -->
      <div class="form-group">
        <label class="form-label">支出分类</label>
        <div class="category-grid">
          <div
            v-for="cat in categoriesL1"
            :key="cat.id"
            class="category-item"
            :class="{ selected: form.category_l1 === cat.name }"
            @click="selectCategoryL1(cat)"
          >
            <span class="cat-icon">{{ cat.icon }}</span>
            <span class="cat-name">{{ cat.name }}</span>
          </div>
        </div>
      </div>

      <!-- 二级分类选择 -->
      <div v-if="categoriesL2.length > 0" class="form-group">
        <label class="form-label">具体分类</label>
        <div class="sub-category-list">
          <el-tag
            v-for="cat in categoriesL2"
            :key="cat.id"
            :type="form.category_l2 === cat.name ? 'primary' : 'info'"
            class="sub-category-tag"
            @click="form.category_l2 = cat.name"
          >
            {{ cat.name }}
          </el-tag>
        </div>
      </div>

      <!-- 备注 -->
      <div class="form-group">
        <label class="form-label">备注（可选）</label>
        <el-input
          v-model="form.note"
          type="textarea"
          :rows="2"
          placeholder="例如：和同事聚餐"
          maxlength="200"
          show-word-limit
        />
      </div>

      <!-- 保存按钮 -->
      <el-button
        type="primary"
        size="large"
        class="save-btn"
        :disabled="!canSave"
        :loading="saving"
        @click="saveExpense"
      >
        {{ saving ? '保存中...' : '💾 保存记录' }}
      </el-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
const form = reactive({
  amount: '',
  date: new Date().toISOString().split('T')[0],
  category_l1: '',
  category_l2: '',
  note: ''
})

const categoriesL1 = ref([])
const categoriesL2 = ref([])
const amountError = ref('')
const saving = ref(false)

// 加载一级分类（通过 Tauri invoke 调用 Rust 后端）
onMounted(async () => {
  try {
    categoriesL1.value = await window.electronAPI.getCategoriesL1()
  } catch (e) {
    ElMessage.error('加载分类失败：' + e)
  }
})

// 选择一级分类时加载二级分类
async function selectCategoryL1(cat) {
  form.category_l1 = cat.name
  form.category_l2 = ''
  try {
    categoriesL2.value = await window.electronAPI.getCategoriesL2(cat.id)
  } catch (e) {
    ElMessage.error('加载子分类失败')
  }
}

function validateAmount() {
  const val = parseFloat(form.amount)
  if (form.amount && (isNaN(val) || val <= 0)) {
    amountError.value = '请输入有效的金额'
  } else if (val > 99999999) {
    amountError.value = '金额不能超过 99,999,999 元'
  } else {
    amountError.value = ''
  }
}

const canSave = computed(() => {
  return (
    form.amount &&
    parseFloat(form.amount) > 0 &&
    !amountError.value &&
    form.date &&
    form.category_l1 &&
    form.category_l2
  )
})

async function saveExpense() {
  if (!canSave.value) return
  saving.value = true

  try {
    await window.electronAPI.addExpense({
      amount: parseFloat(form.amount),
      date: form.date,
      category_l1: form.category_l1,
      category_l2: form.category_l2,
      note: form.note
    })

    ElMessage.success('记账成功！')
    form.amount = ''
    form.category_l1 = ''
    form.category_l2 = ''
    form.note = ''
    categoriesL2.value = []
  } catch (e) {
    ElMessage.error('保存失败：' + e)
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.add-expense-page {
  padding: 16px;
}

.page-header {
  text-align: center;
  margin-bottom: 20px;
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

.form-card {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.form-group {
  margin-bottom: 20px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: #303133;
  margin-bottom: 8px;
}

.amount-input-wrapper {
  display: flex;
  align-items: center;
  border-bottom: 2px solid #e4e7ed;
  padding: 8px 0;
  transition: border-color 0.3s;
}

.amount-input-wrapper:focus-within {
  border-color: #409eff;
}

.currency-symbol {
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  margin-right: 8px;
}

.amount-input {
  flex: 1;
  border: none;
  outline: none;
  font-size: 28px;
  font-weight: 600;
  color: #303133;
  background: transparent;
  -moz-appearance: textfield;
}

.amount-input::-webkit-inner-spin-button,
.amount-input::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.amount-input::placeholder {
  color: #c0c4cc;
  font-weight: 400;
}

.error-text {
  color: #f56c6c;
  font-size: 12px;
  margin: 4px 0 0;
}

.category-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.category-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 10px 4px;
  border-radius: 8px;
  background: #f5f7fa;
  cursor: pointer;
  transition: all 0.2s;
  border: 1.5px solid transparent;
}

.category-item:hover {
  background: #ecf5ff;
}

.category-item.selected {
  background: #ecf5ff;
  border-color: #409eff;
}

.cat-icon {
  font-size: 22px;
  margin-bottom: 4px;
}

.cat-name {
  font-size: 11px;
  color: #606266;
  text-align: center;
  line-height: 1.3;
}

.category-item.selected .cat-name {
  color: #409eff;
  font-weight: 500;
}

.sub-category-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.sub-category-tag {
  cursor: pointer;
  user-select: none;
}

.save-btn {
  width: 100%;
  margin-top: 8px;
  font-size: 16px;
  height: 44px;
}

.full-width-input {
  width: 100%;
}
</style>
