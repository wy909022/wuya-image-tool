<template>
  <!-- 统计页面 — 月度汇总和分类占比 -->
  <div class="stats-page">
    <div class="page-header">
      <h2>📊 支出统计</h2>
    </div>

    <!-- 月份选择 -->
    <div class="month-selector">
      <el-select
        v-model="selectedMonth"
        placeholder="选择月份"
        class="full-width-input"
        @change="loadStats"
      >
        <el-option
          v-for="m in availableMonths"
          :key="m.value"
          :label="m.label"
          :value="m.value"
        />
      </el-select>
    </div>

    <!-- 无数据提示 -->
    <div v-if="!hasData" class="empty-state">
      <p class="empty-icon">📭</p>
      <p class="empty-text">暂无统计数据</p>
      <p class="empty-hint">去"记账"页面添加记录吧</p>
    </div>

    <!-- 统计数据 -->
    <div v-else>
      <!-- 当月汇总 -->
      <div class="summary-card">
        <div class="summary-amount">¥{{ monthTotal.toFixed(2) }}</div>
        <div class="summary-label">{{ summaryLabel }} 总支出</div>
        <div class="summary-count">共 {{ monthCount }} 笔记录</div>
      </div>

      <!-- 分类饼图 -->
      <div class="chart-card">
        <div class="chart-title">分类占比</div>
        <div ref="pieChartRef" class="chart-container"></div>
      </div>

      <!-- 分类排行列表 -->
      <div class="rank-card">
        <div class="chart-title">分类排行</div>
        <div class="rank-list">
          <div
            v-for="(item, index) in categoryStats"
            :key="item.category_l1"
            class="rank-item"
          >
            <div class="rank-left">
              <span class="rank-num" :class="'rank-' + (index + 1)">{{ index + 1 }}</span>
              <div class="rank-info">
                <span class="rank-name">{{ getCategoryIcon(item.category_l1) }} {{ item.category_l1 }}</span>
                <el-progress
                  :percentage="getPercentage(item.total)"
                  :stroke-width="6"
                  :show-text="false"
                  class="rank-progress"
                />
              </div>
            </div>
            <div class="rank-right">
              <span class="rank-amount">¥{{ item.total.toFixed(2) }}</span>
              <span class="rank-count">{{ item.count }}笔</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import dayjs from 'dayjs'

const selectedMonth = ref(dayjs().format('YYYY-MM'))
const availableMonths = ref([])
const categoryStats = ref([])
const categoriesL1 = ref([])
const pieChartRef = ref(null)
let pieChart = null

// 是否有数据
const hasData = computed(() => categoryStats.value.length > 0)

// 当月总支出
const monthTotal = computed(() => {
  return categoryStats.value.reduce((sum, c) => sum + c.total, 0)
})

// 当月笔数
const monthCount = computed(() => {
  return categoryStats.value.reduce((sum, c) => sum + c.count, 0)
})

// 摘要标签
const summaryLabel = computed(() => {
  if (!selectedMonth.value) return ''
  return dayjs(selectedMonth.value + '-01').format('YYYY年M月')
})

// 加载数据
onMounted(async () => {
  try {
    categoriesL1.value = await window.electronAPI.getCategoriesL1()
  } catch (e) {
    console.error('加载分类失败:', e)
  }

  // 获取可用月份列表
  try {
    const monthlyStats = await window.electronAPI.getMonthlyStats()
    availableMonths.value = monthlyStats.map(s => ({
      label: dayjs(s.month + '-01').format('YYYY年M月') + ` (¥${s.total.toFixed(0)})`,
      value: s.month
    }))

    if (availableMonths.value.length > 0) {
      selectedMonth.value = availableMonths.value[0].value
    }
  } catch (e) {
    console.error('加载月度统计失败:', e)
  }

  await loadStats()
})

onUnmounted(() => {
  if (pieChart) {
    pieChart.dispose()
    pieChart = null
  }
})

// 加载统计
async function loadStats() {
  try {
    categoryStats.value = await window.electronAPI.getCategoryStats(selectedMonth.value || undefined)
    await nextTick()
    renderPieChart()
  } catch (e) {
    console.error('加载分类统计失败:', e)
  }
}

// 渲染饼图
function renderPieChart() {
  if (!pieChartRef.value || categoryStats.value.length === 0) return

  if (!pieChart) {
    pieChart = echarts.init(pieChartRef.value)
  }

  const pieData = categoryStats.value.map(c => ({
    name: c.category_l1,
    value: parseFloat(c.total.toFixed(2))
  }))

  pieChart.setOption({
    tooltip: {
      trigger: 'item',
      formatter: '{b}: ¥{c} ({d}%)'
    },
    series: [
      {
        type: 'pie',
        radius: ['50%', '75%'],
        center: ['50%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'outside',
          formatter: '{b}\n{d}%',
          fontSize: 11
        },
        emphasis: {
          label: {
            show: true,
            fontSize: 16,
            fontWeight: 'bold'
          }
        },
        data: pieData
      }
    ]
  })

  window.addEventListener('resize', () => {
    pieChart?.resize()
  })
}

function getPercentage(amount) {
  if (monthTotal.value === 0) return 0
  return Math.round((amount / monthTotal.value) * 100)
}

function getCategoryIcon(name) {
  const cat = categoriesL1.value.find(c => c.name === name)
  return cat ? cat.icon : '📌'
}
</script>

<style scoped>
.stats-page {
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

.month-selector {
  margin-bottom: 16px;
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

.summary-card {
  background: linear-gradient(135deg, #409eff, #337ecc);
  border-radius: 12px;
  padding: 24px;
  text-align: center;
  color: #fff;
  margin-bottom: 16px;
  box-shadow: 0 4px 12px rgba(64, 158, 255, 0.3);
}

.summary-amount {
  font-size: 36px;
  font-weight: 700;
  letter-spacing: 2px;
}

.summary-label {
  font-size: 14px;
  opacity: 0.9;
  margin-top: 4px;
}

.summary-count {
  font-size: 12px;
  opacity: 0.7;
  margin-top: 4px;
}

.chart-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.chart-title {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
  margin-bottom: 12px;
}

.chart-container {
  width: 100%;
  height: 260px;
}

.rank-card {
  background: #fff;
  border-radius: 12px;
  padding: 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.rank-list {
  margin-top: 8px;
}

.rank-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 0;
}

.rank-item:not(:last-child) {
  border-bottom: 1px solid #f5f5f5;
}

.rank-left {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.rank-num {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  background: #c0c4cc;
  flex-shrink: 0;
}

.rank-1 { background: #f56c6c; }
.rank-2 { background: #e6a23c; }
.rank-3 { background: #67c23a; }

.rank-info {
  flex: 1;
  min-width: 0;
}

.rank-name {
  font-size: 14px;
  color: #303133;
}

.rank-progress {
  margin-top: 4px;
}

.rank-right {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  flex-shrink: 0;
  margin-left: 12px;
}

.rank-amount {
  font-size: 15px;
  font-weight: 600;
  color: #303133;
}

.rank-count {
  font-size: 11px;
  color: #909399;
}

.full-width-input {
  width: 100%;
}
</style>
