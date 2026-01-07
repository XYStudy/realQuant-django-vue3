<template>
  <div class="profit-detail-container">
    <header class="page-header">
      <h1>收益详情</h1>
      <el-button @click="$router.back()" type="primary" size="small">返回</el-button>
    </header>
    
    <main class="page-main">
      <el-card>
        <template #header>
          <div class="card-header">
            <span>收益统计</span>
          </div>
        </template>
        
        <el-tabs v-model="activeTab" @tab-change="handleTabChange">
          <el-tab-pane label="当日" name="today">
            <div class="tab-content">
              <el-empty description="当日收益数据" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="上个月" name="lastMonth">
            <div class="tab-content">
              <el-empty description="上个月收益数据" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="近三月" name="lastThreeMonths">
            <div class="tab-content">
              <el-empty description="近三月收益数据" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="近半年" name="lastSixMonths">
            <div class="tab-content">
              <el-empty description="近半年收益数据" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="今年" name="thisYear">
            <div class="tab-content">
              <el-empty description="今年收益数据" />
            </div>
          </el-tab-pane>
          <el-tab-pane label="全部" name="all">
            <div class="tab-content">
              <el-empty description="全部收益数据" />
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-card>
    </main>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const activeTab = ref('today')

const handleTabChange = (tab) => {
  console.log('切换到:', tab)
  // 这里可以根据tab值请求不同时间范围的数据
}
</script>

<style scoped>
.profit-detail-container {
  width: 100%;
  min-height: 100vh;
  background-color: #f5f7fa;
}

.page-header {
  background-color: #409EFF;
  color: white;
  padding: 1rem 2rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.page-header h1 {
  margin: 0;
  font-size: 1.5rem;
}

.page-main {
  padding: 20px;
  max-width: 1200px;
  margin: 0 auto;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tab-content {
  padding: 20px 0;
  text-align: center;
}
</style>