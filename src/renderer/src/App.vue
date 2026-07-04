<template>
  <!-- 应用根组件 — 底部导航布局 -->
  <div class="app-container">
    <!-- 页面内容区域 -->
    <div class="page-content">
      <router-view />
    </div>

    <!-- 底部导航栏 -->
    <div class="bottom-tabs">
      <div
        v-for="tab in tabs"
        :key="tab.path"
        class="tab-item"
        :class="{ active: currentPath === tab.path }"
        @click="switchTab(tab.path)"
      >
        <span class="tab-icon">{{ tab.icon }}</span>
        <span class="tab-label">{{ tab.label }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'

const router = useRouter()
const route = useRoute()
const currentPath = ref(route.path)

const tabs = [
  { path: '/add', label: '记账', icon: '✏️' },
  { path: '/list', label: '账单', icon: '📋' },
  { path: '/stats', label: '统计', icon: '📊' }
]

// 切换底部导航标签
function switchTab(path) {
  currentPath.value = path
  router.push(path)
}

// 监听路由变化，同步高亮
watch(() => route.path, (newPath) => {
  currentPath.value = newPath
})
</script>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f6fa;
}

.page-content {
  flex: 1;
  overflow-y: auto;
  padding-bottom: 16px;
}

/* 底部导航栏 */
.bottom-tabs {
  display: flex;
  justify-content: space-around;
  align-items: center;
  height: 56px;
  background: #ffffff;
  border-top: 1px solid #ebeef5;
  flex-shrink: 0;
}

.tab-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  flex: 1;
  height: 100%;
  cursor: pointer;
  color: #909399;
  transition: color 0.2s;
  user-select: none;
}

.tab-item.active {
  color: #409eff;
}

.tab-icon {
  font-size: 20px;
  line-height: 1.2;
}

.tab-label {
  font-size: 11px;
  margin-top: 2px;
}
</style>
