<template>
  <div class="home-container">
    <!-- 清空数据确认弹窗 -->
    <el-dialog v-model="clearDialogVisible" title="确认清空" width="400px" center>
      <span>您确定要清空所有交易记录吗？此操作不可恢复。</span>
      <template #footer>
        <span class="dialog-footer">
          <el-button @click="cancelClear">取消</el-button>
          <el-button type="danger" @click="clearTradeRecords">确认清空</el-button>
        </span>
      </template>
    </el-dialog>

    <div class="control-panel">
      <el-card class="mt-10">
        <template #header>
          <div class="card-header">
            <span>账户设置</span>
          </div>
        </template>

        <el-form :model="accountSettings" label-width="120px">
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="账户余额(元)">
                <el-input-number v-model="accountSettings.balance" :min="0" :step="1000" style="width: 300px" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="持股数量(股)">
                <el-input-number v-model="accountSettings.shares" :min="0" :step="100" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>
          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="可用持股(股)">
                <el-input-number v-model="accountSettings.availableShares" :min="0" :step="100" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>
          <div class="form-actions">
            <el-button type="primary" @click="saveAccountSettings">保存账户设置</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card>
        <template #header>
          <div class="card-header">
            <span>交易设置</span>
            <el-tag :type="monitoringTimer ? 'success' : 'danger'" size="small">
              {{ monitoringTimer ? '监控中' : '未监控' }}
            </el-tag>
          </div>
        </template>

        <el-form :model="tradeSettings" label-width="120px">
          <el-row :gutter="20">
            <el-col :span="12">
              <el-form-item label="股票代码">
                <el-input v-model="tradeSettings.stockCode" placeholder="如：600000" style="width: 300px" />
              </el-form-item>
            </el-col>
            <el-col :span="12">
              <el-form-item label="更新频率(秒)">
                <el-input-number v-model="tradeSettings.updateInterval" :min="1" :max="60" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="行情阶段" required>
                <el-radio-group v-model="tradeSettings.marketStage">
                  <el-radio label="oscillation">震荡阶段</el-radio>
                  <el-radio label="downward">下跌阶段</el-radio>
                  <el-radio label="upward">上涨阶段</el-radio>
                </el-radio-group>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="tradeSettings.marketStage">
            <el-col :span="24">
              <el-form-item label="交易策略">
                <el-select v-model="tradeSettings.strategy" placeholder="请选择策略" style="width: 300px">
                  <el-option label="格子法做T" value="grid" v-if="tradeSettings.marketStage === 'oscillation'" />
                  <el-option label="百分比做T" value="percentage" v-if="tradeSettings.marketStage === 'oscillation'" />
                </el-select>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="tradeSettings.marketStage === 'oscillation' && tradeSettings.strategy === 'percentage'">
            <el-col :span="24">
              <el-form-item label="高于均价卖出(%)">
                <el-input-number v-model="tradeSettings.sellThreshold" :min="0" :max="10" :step="0.1" style="width: 300px" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label="低于均价买入(%)">
                <el-input-number v-model="tradeSettings.buyThreshold" :min="0" :max="10" :step="0.1" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="tradeSettings.marketStage === 'oscillation' && tradeSettings.strategy === 'grid'">
            <el-col :span="24">
              <el-form-item label-width="150px" label="高于均价格子数卖出">
                <el-input-number v-model="tradeSettings.gridSellCount" :min="1" :max="100" />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label-width="150px" label="低于均价格子数买入">
                <el-input-number v-model="tradeSettings.gridBuyCount" :min="1" :max="100" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="买入金额(元)">
                <el-input-number v-model="tradeSettings.buyAmount" :min="1000" :max="1000000" :step="1000" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="卖出金额(元)">
                <el-input-number v-model="tradeSettings.sellAmount" :min="1000" :max="1000000" :step="1000" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="买入股数(股)">
                <el-input-number v-model="tradeSettings.buyShares" :min="100" :max="100000" :step="100" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="卖出股数(股)">
                <el-input-number v-model="tradeSettings.sellShares" :min="100" :max="100000" :step="100" style="width: 300px" />
              </el-form-item>
            </el-col>
          </el-row>

          <div class="form-actions">
            <el-button type="primary" @click="startMonitoring" :disabled="!tradeSettings.marketStage">开始监控</el-button>
            <el-button @click="stopMonitoring">停止监控</el-button>
          </div>
        </el-form>
      </el-card>

      <el-card class="mt-10">
        <template #header>
          <div class="card-header">
            <span>实时数据</span>
          </div>
        </template>

        <div class="realtime-data">
          <el-row :gutter="20">
            <el-col :span="8">
              <div class="data-item">
                <div class="data-label">当前价格</div>
                <div class="data-value">{{ (Math.floor((realtimeData.currentPrice || 0) * 100) / 100).toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="data-item">
                <div class="data-label">均价</div>
                <div class="data-value">{{ (Math.floor((realtimeData.averagePrice || 0) * 100) / 100).toFixed(2) }}</div>
              </div>
            </el-col>
            <el-col :span="8">
              <div class="data-item">
                <div class="data-label">价格差(%)</div>
                <div class="data-value" :class="getPriceDiffClass">
                  {{ (Math.floor((realtimeData.priceDiff || 0) * 100) / 100).toFixed(2) }}
                </div>
              </div>
            </el-col>
          </el-row>
        </div>
      </el-card>

      <el-card class="mt-10">
        <template #header>
          <div class="card-header">
            <span>数据来源说明</span>
          </div>
        </template>
        <div class="data-source-info">
          <el-alert
            title="注意：当前系统使用模拟数据进行演示"
            type="warning"
            description="在实际生产环境中，您可以接入以下真实金融数据API：
              1. tushare (https://tushare.pro/)
              2. baostock (http://baostock.com/)
              3. 新浪财经API
              4. Yahoo Finance API
              
              修改 backend/quant/services/stock_service.py 文件即可替换数据源。"
            show-icon
            :closable="false"
          />
        </div>
      </el-card>
    </div>

    <div class="chart-panel">
      <el-card class="mt-10">
        <template #header>
          <div class="card-header">
            <span>分时图</span>
          </div>
        </template>
        <div class="chart-container">
          <StockChart 
            :chart-data="chartData" 
            :realtime-data="realtimeData" 
          />
        </div>
      </el-card>

      <el-tabs v-model="activeTab" class="mt-10 trade-tabs">
        <el-tab-pane label="闭环交易" name="loops">
          <el-card>
            <!-- 当前挂起状态 -->
            <div v-if="pendingLoop.type" class="pending-status mb-10">
              <el-alert
                :title="'当前状态: ' + (pendingLoop.type === 'buy_first' ? '已买入，等待卖出闭环' : '已卖出，等待买入闭环')"
                type="info"
                :closable="false"
                show-icon
              >
                <template #default>
                  <div class="mt-5">
                    <span class="mr-10">挂起价格: {{ pendingLoop.price }}</span>
                    <span class="mr-10">挂起数量: {{ pendingLoop.volume }}</span>
                    <span>挂起时间: {{ pendingLoop.timestamp }}</span>
                  </div>
                  <div class="mt-10 flex-align-center">
                    <span class="mr-10">隔夜{{ pendingLoop.type === 'buy_first' ? '卖出' : '买入' }}比例 (%):</span>
                    <el-input-number 
                      v-model="pendingLoop.overnightRatio" 
                      :min="0" 
                      :max="100" 
                      :step="0.1" 
                      size="small"
                      style="width: 120px"
                    />
                    <el-button type="primary" size="small" class="ml-10" @click="saveOvernightRatio">
                      保存隔夜比例
                    </el-button>
                  </div>
                </template>
              </el-alert>
            </div>

            <el-table :data="tradeLoops" style="width: 100%">
              <el-table-column prop="loop_type_display" label="闭环类型" width="120" />
              <el-table-column label="开仓" width="220">
                <template #default="scope">
                  <div>价格: {{ scope.row.open_price }}</div>
                  <div class="text-gray text-small">时间: {{ scope.row.open_time }}</div>
                </template>
              </el-table-column>
              <el-table-column label="平仓" width="220">
                <template #default="scope">
                  <div v-if="scope.row.is_closed">
                    <div>价格: {{ scope.row.close_price }}</div>
                    <div class="text-gray text-small">时间: {{ scope.row.close_time }}</div>
                  </div>
                  <el-tag v-else type="info">进行中</el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="profit" label="盈亏" width="100">
                <template #default="scope">
                  <span :class="scope.row.profit > 0 ? 'price-up' : (scope.row.profit < 0 ? 'price-down' : '')">
                    {{ scope.row.profit }}
                  </span>
                </template>
              </el-table-column>
              <el-table-column label="状态">
                <template #default="scope">
                  <el-tag :type="scope.row.is_closed ? 'success' : 'warning'">
                    {{ scope.row.is_closed ? '已闭环' : '未闭环' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </el-tab-pane>

        <el-tab-pane label="交易记录" name="records">
          <el-card>
            <template #header>
              <div class="card-header">
                <span>历史记录</span>
                <el-button type="danger" size="small" @click="showClearDialog">清空数据</el-button>
              </div>
            </template>
            <el-table :data="tradeRecords" style="width: 100%">
              <el-table-column prop="timestamp" label="时间" width="180" />
              <el-table-column prop="trade_type" label="类型" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.trade_type === 'buy' ? 'success' : 'danger'">
                    {{ scope.row.trade_type === 'buy' ? '买入' : '卖出' }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column prop="price" label="价格" width="100" />
              <el-table-column prop="volume" label="数量" width="100" />
              <el-table-column prop="amount" label="金额" width="120" />
              <el-table-column prop="reason" label="原因" />
            </el-table>
          </el-card>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, watch, inject } from 'vue';
import axios from 'axios';
// 引入股票图表组件
import StockChart from '../components/StockChart.vue';
import { ElMessage } from 'element-plus';

const tradeSettings = reactive({
  stockCode: '603069',
  updateInterval: 5,
  buyAmount: 10000,
  sellAmount: 10000,
  buyShares: null,
  sellShares: null,
  sellThreshold: 0.5,
  buyThreshold: 0.5,
  marketStage: '', // 'oscillation', 'downward', 'upward'
  strategy: 'grid', // 'grid', 'percentage'
  gridBuyCount: 1,
  gridSellCount: 1,
});

const realtimeData = reactive({
  currentPrice: 0,
  averagePrice: 0,
  priceDiff: 0,
  highPrice: 0,
  lowPrice: 0
});

const tradeRecords = ref([]);
const tradeLoops = ref([]);
const activeTab = ref('loops');
const pendingLoop = reactive({
  type: null,
  price: null,
  volume: null,
  timestamp: null,
  overnightRatio: 0
});
const clearDialogVisible = ref(false);
const monitoringTimer = ref(null);
const accountSettings = reactive({
  balance: 100000.0,
  shares: 3000,
  availableShares: 3000,
});
const chartData = reactive({
  time: [],
  price: [],
  average: [],
  price_diff_percent: [], // 价格相对于均价的偏离百分比
});

// WebSocket连接管理
let ws = null;
const isWebSocketConnected = ref(false);

// 监听买入金额变化，自动清空买入股数
watch(
  () => tradeSettings.buyAmount,
  (newVal) => {
    if (newVal !== null && newVal !== undefined) {
      tradeSettings.buyShares = null;
    }
  }
);

// 监听买入股数变化，自动清空买入金额
watch(
  () => tradeSettings.buyShares,
  (newVal) => {
    if (newVal !== null && newVal !== undefined) {
      tradeSettings.buyAmount = null;
    }
  }
);

// 监听卖出金额变化，自动清空卖出股数
watch(
  () => tradeSettings.sellAmount,
  (newVal) => {
    if (newVal !== null && newVal !== undefined) {
      tradeSettings.sellShares = null;
    }
  }
);

// 监听卖出股数变化，自动清空卖出金额
watch(
  () => tradeSettings.sellShares,
  (newVal) => {
    if (newVal !== null && newVal !== undefined) {
      tradeSettings.sellAmount = null;
    }
  }
);



// 更新图表数据
const updateChartData = () => {
  const now = new Date();
  const timeStr = now.toLocaleTimeString();

  // 直接截断到两位小数，不四舍五入
  const currentPrice = Math.floor((realtimeData.currentPrice || 0) * 100) / 100;
  const averagePrice = Math.floor((realtimeData.averagePrice || 0) * 100) / 100;
  
  // 计算价格相对于均价的偏离百分比
  let priceDiffPercent = 0;
  if (averagePrice > 0) {
    priceDiffPercent = (currentPrice - averagePrice) / averagePrice * 100;
    // 直接截断到两位小数，不四舍五入
    priceDiffPercent = Math.floor(priceDiffPercent * 100) / 100;
  }

  chartData.time.push(timeStr);
  chartData.price.push(currentPrice);
  chartData.average.push(averagePrice);
  chartData.price_diff_percent.push(priceDiffPercent);

  // 保持最多100个数据点
  if (chartData.time.length > 100) {
    chartData.time.shift();
    chartData.price.shift();
    chartData.average.shift();
    chartData.price_diff_percent.shift();
  }
};

// 获取价格差样式
const getPriceDiffClass = () => {
  const diff = realtimeData.priceDiff;
  if (diff > 0) return 'price-up';
  if (diff < 0) return 'price-down';
  return '';
};

// 从后端API获取金融数据
const fetchStockData = async () => {
  try {
    // 调用后端API获取真实数据
    const response = await axios.get(`/api/stock/${tradeSettings.stockCode}`);
    const data = response.data;

    realtimeData.currentPrice = data.current_price;
    realtimeData.averagePrice = data.average_price;
    realtimeData.priceDiff = data.price_diff_percent;
    
    // 更新账户信息
    if (data.account) {
      accountSettings.balance = data.account.balance;
      accountSettings.shares = data.account.shares;
      accountSettings.availableShares = data.account.available_shares;
    }

    updateChart();

    // 获取最新的交易记录
    await fetchTradeRecords();
    await fetchTradeLoops();
  } catch (error) {
    console.error('获取股票数据失败:', error);
  }
};

// 从后端获取交易记录
const fetchTradeRecords = async () => {
  if (!tradeSettings.stockCode || tradeSettings.stockCode.length !== 6) return;
  try {
    const response = await axios.get(`/api/trade-records/${tradeSettings.stockCode}/`);
    tradeRecords.value = response.data;

    // 计算盈利
    calculateProfit(response.data);
  } catch (error) {
    console.error('获取交易记录失败:', error);
  }
};

// 从后端获取闭环交易记录
const fetchTradeLoops = async () => {
  if (!tradeSettings.stockCode || tradeSettings.stockCode.length !== 6) return;
  try {
    const response = await axios.get(`/api/trade-loops/${tradeSettings.stockCode}/`);
    tradeLoops.value = response.data;
  } catch (error) {
    console.error('获取闭环交易记录失败:', error);
  }
};

// 从父组件注入盈利信息
const profitInfo = inject(
  'profitInfo',
  reactive({
    type: '',
    amount: 0,
    unit: '',
    status: '',
  })
);

// 计算交易闭环的盈利
const calculateProfit = (records) => {
  if (!records || records.length < 2) {
    profitInfo.type = '';
    profitInfo.amount = 0;
    profitInfo.unit = '';
    profitInfo.status = '';
    return;
  }

  // 按时间排序，最新的在前面
  const sortedRecords = [...records].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  // 计算所有买入和卖出交易的盈利总和
  let totalBuyAmount = 0;
  let totalSellAmount = 0;
  let buyCount = 0;
  let sellCount = 0;

  for (const record of sortedRecords) {
    if (record.trade_type === 'buy') {
      totalBuyAmount += record.amount;
      buyCount++;
    } else if (record.trade_type === 'sell') {
      totalSellAmount += record.amount;
      sellCount++;
    }
  }

  // 计算总盈利
  let totalProfit = totalSellAmount - totalBuyAmount;
  let unit = '元';
  let type = '总盈亏';

  // 确定盈利状态
  let status = '';
  if (totalProfit > 0) {
    status = '盈利';
  } else if (totalProfit < 0) {
    status = '亏损';
  } else {
    status = '持平';
  }

  // 直接更新注入的盈利信息
  profitInfo.type = type;
  profitInfo.amount = parseFloat(totalProfit.toFixed(2));
  profitInfo.unit = unit;
  profitInfo.status = status;
};

// 获取初始化账户信息
const fetchAccountSettings = async () => {
  try {
    // 保存账户设置到后端
    await axios.post(`/api/account/`, {
      stock_code: tradeSettings.stockCode,
      balance: accountSettings.balance,
      shares: accountSettings.shares,
      available_shares: accountSettings.availableShares,
    });
  } catch (error) {
    console.error('获取账户设置失败:', error);
    ElMessage.error('获取账户设置失败，请检查网络连接');
  }
};

// WebSocket连接函数
const connectWebSocket = async () => {
  try {
    // 先保存账户设置到后端
    await fetchAccountSettings();
    
    // 保存交易设置到后端
    await axios.post('/api/trade-setting/', {
      stock_code: tradeSettings.stockCode,
      sell_threshold: tradeSettings.sellThreshold,
      buy_threshold: tradeSettings.buyThreshold,
      buy_amount: tradeSettings.buyAmount,
      sell_amount: tradeSettings.sellAmount,
      buy_shares: tradeSettings.buyShares,
      sell_shares: tradeSettings.sellShares,
      update_interval: tradeSettings.updateInterval,
      market_stage: tradeSettings.marketStage,
      strategy: tradeSettings.strategy,
      grid_buy_count: tradeSettings.gridBuyCount,
      grid_sell_count: tradeSettings.gridSellCount,
    });

    // 确保stockCode是字符串类型
    const stockCodeStr = String(tradeSettings.stockCode).trim();
    console.log('DEBUG: stockCodeStr:', stockCodeStr);
    
    // 构建WebSocket URL，直接指向后端服务器
    const wsUrl = `ws://localhost:8000/ws/stock/${stockCodeStr}/`;
    console.log('DEBUG: WebSocket URL:', wsUrl);

    // 关闭现有连接（如果存在）
    if (ws) {
      console.log('DEBUG: Closing existing WebSocket connection');
      ws.close();
    }

    // 创建新的WebSocket连接
    console.log('DEBUG: Creating WebSocket connection...');
    try {
      ws = new WebSocket(wsUrl);
      console.log('DEBUG: WebSocket object created successfully');
      console.log('DEBUG: WebSocket readyState:', ws.readyState);
    } catch (error) {
      console.error('DEBUG: WebSocket creation failed:', error);
      ElMessage.error(`WebSocket连接创建失败: ${error.message}`);
      return;
    }

    // 连接打开事件
    ws.onopen = () => {
      console.log('WebSocket连接已建立');
      isWebSocketConnected.value = true;
      
      // 发送开始监控消息
      ws.send(JSON.stringify({
        type: 'start_monitoring'
      }));
      
      ElMessage.success('已连接到WebSocket服务器，开始监控');
    };

    // 接收消息事件
    ws.onmessage = (event) => {
      console.log('WebSocket收到消息:', event.data);
      try {
        const message = JSON.parse(event.data);
        handleWebSocketMessage(message);
      } catch (error) {
        console.error('WebSocket消息解析失败:', error);
        console.error('原始消息:', event.data);
        ElMessage.error('WebSocket消息解析失败');
      }
    };

    // 连接关闭事件
    ws.onclose = (event) => {
      console.log('WebSocket连接已关闭:', event.code, event.reason);
      console.log('关闭事件详情:', event);
      isWebSocketConnected.value = false;
      ElMessage.warning(`WebSocket连接已关闭: ${event.code} - ${event.reason}`);
    };

    // 连接错误事件
    ws.onerror = (event) => {
      console.error('WebSocket连接错误:', event);
      console.error('错误事件详情:', JSON.stringify(event));
      isWebSocketConnected.value = false;
      
      // 获取更详细的错误信息
      let errorMessage = 'WebSocket连接失败';
      if (event.message) {
        errorMessage += `: ${event.message}`;
      } else if (event.type) {
        errorMessage += `: ${event.type}`;
      }
      
      errorMessage += ' - 请检查网络连接和服务器状态';
      
      // 显示错误信息
      ElMessage.error(errorMessage);
    };
  } catch (error) {
    console.error('连接WebSocket失败:', error);
    ElMessage.error('保存设置失败，请检查网络连接');
  }
};

// WebSocket消息处理函数
const handleWebSocketMessage = (message) => {
  switch (message.type) {
    case 'stock_data':
      // 更新实时数据
      realtimeData.currentPrice = message.stock_data.current_price;
      realtimeData.averagePrice = message.stock_data.average_price;
      realtimeData.priceDiff = message.stock_data.price_diff_percent;
      realtimeData.highPrice = message.stock_data.high || message.stock_data.current_price;
      realtimeData.lowPrice = message.stock_data.low || message.stock_data.current_price;
      
      // 更新账户信息
      if (message.account) {
        accountSettings.balance = message.account.balance;
        accountSettings.shares = message.account.shares;
        accountSettings.availableShares = message.account.available_shares;
      }
      
      // 更新交易记录
      if (message.trade_records) {
        tradeRecords.value = message.trade_records;
        calculateProfit(message.trade_records);
      }
      
      // 更新闭环交易数据
      if (message.trade_loops) {
        tradeLoops.value = message.trade_loops;
      }
      
      // 更新挂起状态
      if (message.trade_setting) {
        pendingLoop.type = message.trade_setting.pending_loop_type;
        pendingLoop.price = message.trade_setting.pending_price;
        pendingLoop.volume = message.trade_setting.pending_volume;
        pendingLoop.timestamp = message.trade_setting.pending_timestamp;
        
        if (pendingLoop.type === 'buy_first') {
          pendingLoop.overnightRatio = message.trade_setting.overnight_sell_ratio;
        } else if (pendingLoop.type === 'sell_first') {
          pendingLoop.overnightRatio = message.trade_setting.overnight_buy_ratio;
        }
      }
      
      // 更新图表数据
      updateChartData();
      break;
    case 'monitoring_status':
      console.log('监控状态:', message.status);
      break;
    case 'error':
      console.error('WebSocket错误:', message.message);
      ElMessage.error(message.message);
      break;
    default:
      console.log('未知消息类型:', message.type);
  }
};

// 断开WebSocket连接
const disconnectWebSocket = () => {
  if (ws) {
    // 发送停止监控消息
    ws.send(JSON.stringify({
      type: 'stop_monitoring'
    }));
    
    // 关闭连接
    ws.close();
    ws = null;
    isWebSocketConnected.value = false;
    console.log('WebSocket连接已断开');
  }
};

// 开始监控
const startMonitoring = async () => {
  // 停止现有的HTTP轮询（如果存在）
  if (monitoringTimer.value) {
    clearInterval(monitoringTimer.value);
    monitoringTimer.value = null;
  }
  
  // 连接WebSocket
  await connectWebSocket();
};

// 停止监控
const stopMonitoring = () => {
  console.log('停止监控');
  
  // 停止旧的HTTP轮询（如果存在）
  if (monitoringTimer.value) {
    clearInterval(monitoringTimer.value);
    monitoringTimer.value = null;
  }
  
  // 断开WebSocket连接
  disconnectWebSocket();
};

// 保存账户设置
const saveAccountSettings = async () => {
  try {
    await axios.post(`/api/account/`, {
      stock_code: tradeSettings.stockCode,
      balance: accountSettings.balance,
      shares: accountSettings.shares,
      available_shares: accountSettings.availableShares,
    });

    ElMessage.success('账户设置保存成功');
  } catch (error) {
    console.error('保存账户设置失败:', error);
    ElMessage.error('保存账户设置失败，请检查网络连接');
  }
};

// 保存隔夜比例
const saveOvernightRatio = async () => {
  try {
    const data = {
      stock_code: tradeSettings.stockCode,
    };
    if (pendingLoop.type === 'buy_first') {
      data.overnight_sell_ratio = pendingLoop.overnightRatio;
    } else if (pendingLoop.type === 'sell_first') {
      data.overnight_buy_ratio = pendingLoop.overnightRatio;
    }
    
    await axios.post('/api/trade-setting/', data);
    ElMessage.success('隔夜比例保存成功');
  } catch (error) {
    console.error('保存隔夜比例失败:', error);
    ElMessage.error('保存隔夜比例失败');
  }
};

// 显示清空数据弹窗
const showClearDialog = () => {
  clearDialogVisible.value = true;
};

// 取消清空数据
const cancelClear = () => {
  clearDialogVisible.value = false;
};

// 清空交易记录
const clearTradeRecords = async () => {
  try {
    // 调用后端API清空交易记录
    await axios.delete(`/api/trade-records/${tradeSettings.stockCode}/`);

    // 清空前端交易记录
    tradeRecords.value = [];
    tradeLoops.value = [];

    // 清空盈利信息
    profitInfo.value = {
      type: '',
      amount: 0,
      unit: '',
      status: '',
    };

    // 关闭弹窗
    clearDialogVisible.value = false;

    // 显示成功消息
    ElMessage.success('交易记录已清空');
  } catch (error) {
    console.error('清空交易记录失败:', error);
    ElMessage.error('清空交易记录失败，请检查网络连接');
  }
};

// 监听股票代码变化，当长度为6位时自动加载数据
watch(
  () => tradeSettings.stockCode,
  (newVal) => {
    if (newVal && newVal.length === 6) {
      fetchTradeRecords();
      fetchTradeLoops();
    }
  }
);

onMounted(() => {
  // 页面加载时，如果已有6位代码，则加载数据
  if (tradeSettings.stockCode && tradeSettings.stockCode.length === 6) {
    fetchTradeRecords();
    fetchTradeLoops();
  }
});

onUnmounted(() => {
  stopMonitoring();
});
</script>

<style scoped>
.home-container {
  display: flex;
  gap: 20px;
  max-width: 1600px;
  margin: 0 auto;
}

.control-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.chart-panel {
  flex: 2;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.form-actions {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

.realtime-data {
  padding: 20px 0;
}

.data-item {
  text-align: center;
}

.data-label {
  font-size: 0.9rem;
  color: #606266;
  margin-bottom: 5px;
}

.data-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: #303133;
}

.price-up {
  color: #f56c6c;
}

.price-down {
  color: #67c23a;
}

.chart-container {
  width: 100%;
  height: 400px;
}

.mt-20 {
  margin-top: 20px;
}

.mb-10 {
  margin-bottom: 10px;
}

.ml-10 {
  margin-left: 10px;
}

.mr-10 {
  margin-right: 10px;
}

.flex-align-center {
  display: flex;
  align-items: center;
}

.text-gray {
  color: #909399;
}

.text-small {
  font-size: 0.85rem;
}

.trade-tabs :deep(.el-tabs__content) {
  padding: 0;
}

.trade-tabs :deep(.el-tabs__header) {
  margin-bottom: 0;
  background: #fff;
  padding: 0 20px;
  border-radius: 4px 4px 0 0;
}

.data-source-info {
  margin-bottom: 0;
}

.data-source-info .el-alert__description {
  margin: 10px 0 0 0;
  white-space: pre-line;
  font-size: 0.9rem;
}

/* 为el-input-number组件设置固定宽度 */
:deep(.el-input-number) {
  width: 300px !important;
}

/* 确保输入框部分也占满宽度 */
:deep(.el-input-number__input-wrap) {
  flex: 1;
}
</style>
