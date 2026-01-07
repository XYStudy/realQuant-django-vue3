<template>
  <div class="app-container">
    <header class="app-header">
      <h1>
        量化交易系统
        <span class="profit-container">
          <!-- 盈利信息 -->
          <el-dropdown @command="handleProfitCommand">
            <div class="profit-info-content">
              <span class="profit-label">当日盈亏:</span>
              <span class="profit-value" :class="profitInfo.amount >= 0 ? 'profit-positive' : 'profit-negative'">
                {{ profitInfo.amount >= 0 ? '+' : '' }}{{ profitInfo.amount }}{{ profitInfo.unit }}
              </span>
              <el-icon class="el-icon--right"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="detail">查看详情</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </span>
      </h1>
    </header>
    
    <main class="app-main">
      <router-view v-slot="{ Component }">
        <transition name="fade" mode="out-in">
          <component :is="Component" />
        </transition>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, reactive, provide, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ArrowDown } from '@element-plus/icons-vue'

const router = useRouter()

// 全局盈利信息，使用reactive对象以便在组件间共享
const profitInfo = reactive({
  type: '',
  amount: 0,
  unit: '',
  status: ''
})

// 提供盈利信息给子组件
provide('profitInfo', profitInfo)

// 处理盈利信息下拉菜单命令
const handleProfitCommand = (command) => {
  if (command === 'detail') {
    // 跳转到盈利详情页面
    router.push('/profit/detail')
  }
}
</script>

<style scoped>
.app-container {
  width: 100%;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.app-header {
  background-color: #409EFF;
  color: white;
  padding: 1rem 2rem;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.app-header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.app-main {
  padding: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

/* 盈利信息样式 */
.profit-container {
  margin-left: 20px;
}

.profit-info-content {
  display: flex;
  align-items: center;
  cursor: pointer;
  padding: 8px 16px;
  background-color: rgba(255, 255, 255, 0.15);
  border: 1px solid rgba(255, 255, 255, 0.3);
  border-radius: 20px;
  transition: all 0.3s ease;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  outline: none;
  box-sizing: border-box;
}

.profit-info-content:hover {
  background-color: rgba(255, 255, 255, 0.25);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  transform: translateY(-1px);
  border-color: rgba(255, 255, 255, 0.4);
}

/* 移除dropdown组件的默认hover边框 */
:deep(.el-dropdown__trigger:focus) .profit-info-content,
:deep(.el-dropdown__trigger:hover) .profit-info-content {
  outline: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

/* 移除所有可能的焦点边框 */
:deep(.el-dropdown__trigger) {
  outline: none;
}

:deep(.el-dropdown__trigger:focus-visible) {
  outline: none;
}

.profit-label {
  margin-right: 8px;
  font-size: 14px;
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.profit-value {
  font-size: 18px;
  font-weight: bold;
  margin-right: 4px;
  letter-spacing: 0.5px;
}

.profit-positive {
  color: #95DE64;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

.profit-negative {
  color: #FF7875;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* 零值样式 - 提高对比度 */
.profit-value.profit-positive[style*="+0"] {
  color: #E6A23C;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.2);
}

/* 过渡动画 */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.3s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>