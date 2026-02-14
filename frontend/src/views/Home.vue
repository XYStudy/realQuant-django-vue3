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
            <el-tag :type="isMonitoring ? 'success' : 'danger'" size="small">
              {{ isMonitoring ? '监控中' : '未监控' }}
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
          <el-row :gutter="20" v-if="tradeSettings.marketStage === 'oscillation'">
            <el-col :span="24">
              <el-form-item required>
                <template #label>
                  <div class="label-with-help">
                    <span>震荡类型</span>
                    <el-tooltip content="低位震荡只能买->卖，普通震荡可以买->卖/卖->买。" placement="top">
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </template>
                <el-radio-group v-model="tradeSettings.oscillationType">
                  <el-radio label="low">低位震荡</el-radio>
                  <el-radio label="normal">普通震荡</el-radio>
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
                <el-input 
                  v-model.number="tradeSettings.gridSellCount" 
                  type="number"
                  placeholder=""
                  clearable
                  style="width: 300px"
                  :disabled="(tradeSettings.sellAvgLineRangeMinus !== null && tradeSettings.sellAvgLineRangeMinus !== undefined && tradeSettings.sellAvgLineRangeMinus !== '') || (tradeSettings.sellAvgLineRangePlus !== null && tradeSettings.sellAvgLineRangePlus !== undefined && tradeSettings.sellAvgLineRangePlus !== '')"
                />
              </el-form-item>
            </el-col>
            <el-col :span="24">
              <el-form-item label-width="150px" label="低于均价格子数买入">
                <el-input 
                  v-model.number="tradeSettings.gridBuyCount" 
                  type="number"
                  placeholder=""
                  clearable
                  style="width: 300px"
                  :disabled="(tradeSettings.buyAvgLineRangeMinus !== null && tradeSettings.buyAvgLineRangeMinus !== undefined && tradeSettings.buyAvgLineRangeMinus !== '') || (tradeSettings.buyAvgLineRangePlus !== null && tradeSettings.buyAvgLineRangePlus !== undefined && tradeSettings.buyAvgLineRangePlus !== '')"
                />
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="tradeSettings.strategy === 'grid'">
            <el-col :span="24">
              <el-form-item>
                <template #label>
                  <div class="label-with-help">
                    <span>均价线附近买入</span>
                    <el-tooltip content="设置买入时的成交范围。左边框输入均价线以下的格子数，右边框输入均价线以上的格子数。例如左边0.1右边0.1，则在[均价线-0.1格, 均价线+0.1格]范围内均可买入。" placement="top">
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </template>
                <div class="flex-align-center range-config-container">
                  <span class="range-symbol minus-symbol" style="color: #67c23a; font-size: 1.4rem; font-weight: bold;">-</span>
                  <el-input 
                    v-model="tradeSettings.buyAvgLineRangeMinus" 
                    :precision="2" 
                    class="range-input" 
                    style="width: 100px !important;" 
                    :disabled="tradeSettings.gridBuyCount !== null && tradeSettings.gridBuyCount !== undefined && tradeSettings.gridBuyCount !== ''"
                    placeholder=""
                    clearable
                  />
                  <span class="center-text" style="margin: 0 15px; font-weight: bold;">均价线</span>
                  <el-input 
                    v-model="tradeSettings.buyAvgLineRangePlus" 
                    :precision="2" 
                    class="range-input" 
                    style="width: 100px !important;" 
                    :disabled="tradeSettings.gridBuyCount !== null && tradeSettings.gridBuyCount !== undefined && tradeSettings.gridBuyCount !== ''"
                    placeholder=""
                    clearable
                  />
                  <span class="range-symbol plus-symbol" style="color: #f56c6c; font-size: 1.4rem; font-weight: bold;">+</span>
                </div>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20" v-if="tradeSettings.strategy === 'grid'">
            <el-col :span="24">
              <el-form-item>
                <template #label>
                  <div class="label-with-help">
                    <span>均价线附近卖出</span>
                    <el-tooltip content="设置卖出时的成交范围。左边框输入均价线以下的格子数，右边框输入均价线以上的格子数。例如左边0.1右边0.1，则在[均价线-0.1格, 均价线+0.1格]范围内均可卖出。" placement="top">
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </div>
                </template>
                <div class="flex-align-center range-config-container">
                  <span class="range-symbol minus-symbol" style="color: #67c23a; font-size: 1.4rem; font-weight: bold;">-</span>
                  <el-input 
                    v-model="tradeSettings.sellAvgLineRangeMinus" 
                    :precision="2" 
                    class="range-input" 
                    style="width: 100px !important;" 
                    :disabled="tradeSettings.gridSellCount !== null && tradeSettings.gridSellCount !== undefined && tradeSettings.gridSellCount !== ''"
                    placeholder=""
                    clearable
                  />
                  <span class="center-text" style="margin: 0 15px; font-weight: bold;">均价线</span>
                  <el-input 
                    v-model="tradeSettings.sellAvgLineRangePlus" 
                    :precision="2" 
                    class="range-input" 
                    style="width: 100px !important;" 
                    :disabled="tradeSettings.gridSellCount !== null && tradeSettings.gridSellCount !== undefined && tradeSettings.gridSellCount !== ''"
                    placeholder=""
                    clearable
                  />
                  <span class="range-symbol plus-symbol" style="color: #f56c6c; font-size: 1.4rem; font-weight: bold;">+</span>
                </div>
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

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="数据记录">
                <el-checkbox v-model="tradeSettings.recordData">监控时存储原始数据</el-checkbox>
                <el-tooltip content="开启后，停止监控时会将 API 原始响应保存为 JSON 文件。" placement="top">
                  <el-icon class="help-icon"><QuestionFilled /></el-icon>
                </el-tooltip>
              </el-form-item>
            </el-col>
          </el-row>

          <el-row :gutter="20">
            <el-col :span="24">
              <el-form-item label="回测文件路径">
                <el-input v-model="tradeSettings.mockFilePath" placeholder="如：F:\traeProject\2026-01-30-603069-海汽集团.json" style="width: 100%">
                  <template #append>
                    <el-tooltip content="留空则请求真实接口。输入完整路径后，监控将从该文件读取数据。" placement="top">
                      <el-icon class="help-icon"><QuestionFilled /></el-icon>
                    </el-tooltip>
                  </template>
                </el-input>
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
import { ElMessage, ElMessageBox } from 'element-plus';
import { QuestionFilled } from '@element-plus/icons-vue';

const tradeSettings = reactive({
  stockCode: '603069',
  updateInterval: 5,
  buyShares: null,
  sellShares: null,
  sellThreshold: 0.5,
  buyThreshold: 0.5,
  marketStage: 'oscillation', // 'oscillation', 'downward', 'upward'
  oscillationType: 'normal', // 'low', 'normal'
  strategy: 'grid', // 'grid', 'percentage'
  gridBuyCount: null,
  gridSellCount: null,
  buyAvgLineRangeMinus: null,
  buyAvgLineRangePlus: null,
  sellAvgLineRangeMinus: null,
  sellAvgLineRangePlus: null,
  recordData: false,
  mockFilePath: '',
  overnightSellRatio: 1.0,
  overnightBuyRatio: 1.0,
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
  overnightRatio: 1.0
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
const isMonitoring = ref(false);

// 过滤辅助函数：将 undefined 和空字符串转换为 null，以便后端能够识别并清空数据库字段
const filterEmptyFields = (obj) => {
  const newObj = {};
  Object.keys(obj).forEach(key => {
    const value = obj[key];
    if (value === undefined || value === '') {
      newObj[key] = null;
    } else {
      newObj[key] = value;
    }
  });
  return newObj;
};

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

    updateChartData();

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
    
    // 检查是否有未闭环的交易，如果前端挂起状态为空，则尝试从闭环记录恢复
    const unclosedLoop = tradeLoops.value.find(loop => !loop.is_closed);
    if (unclosedLoop && !pendingLoop.type) {
      pendingLoop.type = unclosedLoop.loop_type === 'buy_sell' ? 'buy_first' : 'sell_first';
      pendingLoop.price = unclosedLoop.open_price;
      pendingLoop.volume = unclosedLoop.open_volume; // 注意：需要后端返回这个字段
      pendingLoop.timestamp = unclosedLoop.open_time;
      
      // 这里的 overnightRatio 会在 fetchTradeSetting 中获取，或者保持默认 1.0
      console.log('从闭环交易记录中恢复挂起状态:', pendingLoop.type);
    }
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
  if (!records || records.length === 0) {
    profitInfo.type = '';
    profitInfo.amount = 0;
    profitInfo.unit = '';
    profitInfo.status = '';
    return;
  }

  // 按时间排序，最新的在前面
  const sortedRecords = [...records].sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

  // 计算所有买入和卖出交易的盈亏总和
  let totalProfit = 0;

  for (const record of sortedRecords) {
    if (record.trade_type === 'sell') {
      totalProfit += record.amount;
    } else if (record.trade_type === 'buy') {
      totalProfit -= record.amount;
    }
  }

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

// 获取账户设置
const fetchAccountSettings = async () => {
  if (!tradeSettings.stockCode || tradeSettings.stockCode.length !== 6) return;
  try {
    const response = await axios.get(`/api/account/?stock_code=${tradeSettings.stockCode}`);
    if (response.data) {
      accountSettings.balance = response.data.balance;
      accountSettings.shares = response.data.shares;
      accountSettings.availableShares = response.data.available_shares;
    }
  } catch (error) {
    console.error('获取账户设置失败:', error);
  }
};

// WebSocket连接函数
const connectWebSocket = async () => {
  try {
    // 先保存账户设置到后端
    await fetchAccountSettings();
    
    // 保存交易设置到后端
    const tradeSettingData = filterEmptyFields({
      stock_code: tradeSettings.stockCode,
      sell_threshold: tradeSettings.sellThreshold,
      buy_threshold: tradeSettings.buyThreshold,
      buy_shares: tradeSettings.buyShares,
      sell_shares: tradeSettings.sellShares,
      update_interval: tradeSettings.updateInterval,
      market_stage: tradeSettings.marketStage,
      oscillation_type: tradeSettings.oscillationType,
      buy_avg_line_range_minus: tradeSettings.buyAvgLineRangeMinus,
      buy_avg_line_range_plus: tradeSettings.buyAvgLineRangePlus,
      sell_avg_line_range_minus: tradeSettings.sellAvgLineRangeMinus,
      sell_avg_line_range_plus: tradeSettings.sellAvgLineRangePlus,
      strategy: tradeSettings.strategy,
      grid_buy_count: tradeSettings.gridBuyCount,
      grid_sell_count: tradeSettings.gridSellCount,
    });
    
    await axios.post('/api/trade-setting/', tradeSettingData);

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
        type: 'start_monitoring',
        record_data: tradeSettings.recordData,
        mock_file_path: tradeSettings.mockFilePath
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
      isMonitoring.value = false;
      ElMessage.warning(`WebSocket连接已关闭: ${event.code} - ${event.reason}`);
    };

    // 连接错误事件
    ws.onerror = (event) => {
      console.error('WebSocket连接错误:', event);
      console.error('错误事件详情:', JSON.stringify(event));
      isWebSocketConnected.value = false;
      isMonitoring.value = false;
      
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
      }
      
      // 更新图表数据
      updateChartData();
      break;
    case 'monitoring_status':
      console.log('监控状态:', message.status);
      isMonitoring.value = (message.status === 'started');
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
  // 校验卖出股数是否大于可用持股
  if (tradeSettings.sellShares && accountSettings.availableShares && tradeSettings.sellShares > accountSettings.availableShares) {
    try {
      await ElMessageBox.confirm(
        `当前卖出设置 (${tradeSettings.sellShares}股) 大于可用持股 (${accountSettings.availableShares}股)，系统可能无法执行卖出交易。是否继续？`,
        '持仓不足提醒',
        {
          confirmButtonText: '确定继续',
          cancelButtonText: '取消',
          type: 'warning',
        }
      );
    } catch (error) {
      // 用户点击取消，直接返回
      return;
    }
  }

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
  isMonitoring.value = false;
  
  // 停止旧的HTTP轮询（如果存在）
  if (monitoringTimer.value) {
    clearInterval(monitoringTimer.value);
    monitoringTimer.value = null;
  }
  
  // 断开WebSocket连接
  disconnectWebSocket();
};

// 保存账户设置到后端
const saveAccountSettings = async () => {
  try {
    const accountData = filterEmptyFields({
      stock_code: tradeSettings.stockCode,
      balance: accountSettings.balance,
      shares: accountSettings.shares,
      available_shares: accountSettings.availableShares,
    });
    
    await axios.post(`/api/account/`, accountData);
    ElMessage.success('账户设置已保存');
  } catch (error) {
    console.error('保存账户设置失败:', error);
    ElMessage.error('保存账户设置失败');
  }
};

// 保存隔夜比例
const saveOvernightRatio = async () => {
  try {
    const data = {
      stock_code: tradeSettings.stockCode,
      overnight_sell_ratio: null,
      overnight_buy_ratio: null,
    };
    
    // 如果存在挂起任务，根据挂起类型只更新对应的比例，另一个传 null
    if (pendingLoop.type === 'buy_first') {
      data.overnight_sell_ratio = pendingLoop.overnightRatio;
      tradeSettings.overnightSellRatio = pendingLoop.overnightRatio;
    } else if (pendingLoop.type === 'sell_first') {
      data.overnight_buy_ratio = pendingLoop.overnightRatio;
      tradeSettings.overnightBuyRatio = pendingLoop.overnightRatio;
    } else {
      // 如果没有挂起任务，则使用 tradeSettings 中的值
      data.overnight_sell_ratio = tradeSettings.overnightSellRatio;
      data.overnight_buy_ratio = tradeSettings.overnightBuyRatio;
    }
    
    console.log('DEBUG: 准备保存的隔夜比例数据:', data);
    await axios.post('/api/trade-setting/', data);
    
    ElMessage.success('隔夜比例保存成功');
    // 保存后重新获取一次设置，确保状态一致
    await fetchTradeSetting();
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
    
    // 清空前端挂起状态
    pendingLoop.type = null;
    pendingLoop.price = null;
    pendingLoop.volume = null;
    pendingLoop.timestamp = null;

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

// 从后端获取交易设置
const fetchTradeSetting = async () => {
  if (!tradeSettings.stockCode || tradeSettings.stockCode.length !== 6) return;
  try {
    const response = await axios.get(`/api/trade-setting/`, {
      params: { stock_code: tradeSettings.stockCode }
    });
    const data = response.data.data;
    console.log('DEBUG: 获取到的交易设置数据:', data);
    
    // 更新本地设置
    tradeSettings.sellThreshold = data.sell_threshold;
    tradeSettings.buyThreshold = data.buy_threshold;
    tradeSettings.buyShares = data.buy_shares;
    tradeSettings.sellShares = data.sell_shares;
    tradeSettings.updateInterval = data.update_interval;
    tradeSettings.marketStage = data.market_stage || 'oscillation';
    tradeSettings.oscillationType = data.oscillation_type || 'normal';
    tradeSettings.strategy = data.strategy || 'grid';
    tradeSettings.gridBuyCount = data.grid_buy_count;
    tradeSettings.gridSellCount = data.grid_sell_count;
    tradeSettings.buyAvgLineRangeMinus = data.buy_avg_line_range_minus;
    tradeSettings.buyAvgLineRangePlus = data.buy_avg_line_range_plus;
    tradeSettings.sellAvgLineRangeMinus = data.sell_avg_line_range_minus;
    tradeSettings.sellAvgLineRangePlus = data.sell_avg_line_range_plus;

    // 更新挂起状态和隔夜比例
    if (data.pending_loop_type) {
      pendingLoop.type = data.pending_loop_type;
      pendingLoop.price = data.pending_price;
      pendingLoop.volume = data.pending_volume;
      pendingLoop.timestamp = data.pending_timestamp;
    } else {
      pendingLoop.type = null;
      pendingLoop.price = null;
      pendingLoop.volume = null;
      pendingLoop.timestamp = null;
    }

    // 保存后端返回的比例到本地，以便切换显示
    if (data.overnight_sell_ratio !== undefined) {
      tradeSettings.overnightSellRatio = data.overnight_sell_ratio !== null ? Number(data.overnight_sell_ratio) : 1.0;
    }
    if (data.overnight_buy_ratio !== undefined) {
      tradeSettings.overnightBuyRatio = data.overnight_buy_ratio !== null ? Number(data.overnight_buy_ratio) : 1.0;
    }

    // 根据当前挂起类型显示对应的比例
    if (pendingLoop.type === 'sell_first') {
      pendingLoop.overnightRatio = tradeSettings.overnightBuyRatio;
    } else {
      // 默认为 buy_first 或无任务时显示卖出比例
      pendingLoop.overnightRatio = tradeSettings.overnightSellRatio;
    }
    
    // 如果没有 pendingLoop.type，说明目前没有未闭环任务，则不锁定输入框
    if (!pendingLoop.type) {
      tradeSettings.gridSellCount = data.grid_sell_count;
      tradeSettings.gridBuyCount = data.grid_buy_count;
      tradeSettings.sellAvgLineRangeMinus = data.sell_avg_line_range_minus;
      tradeSettings.sellAvgLineRangePlus = data.sell_avg_line_range_plus;
      tradeSettings.buyAvgLineRangeMinus = data.buy_avg_line_range_minus;
      tradeSettings.buyAvgLineRangePlus = data.buy_avg_line_range_plus;
    }

    console.log('DEBUG: 处理后的比例 - 卖出:', tradeSettings.overnightSellRatio, '买入:', tradeSettings.overnightBuyRatio, '当前显示:', pendingLoop.overnightRatio);
  } catch (error) {
    console.error('获取交易设置失败:', error);
  }
};

// 监听股票代码变化
watch(() => tradeSettings.stockCode, (newVal) => {
  if (newVal && newVal.length === 6) {
    fetchStockData();
    fetchAccountSettings();
    fetchTradeSetting();
    fetchTradeRecords();
    fetchTradeLoops();
  }
});

onMounted(() => {
  if (tradeSettings.stockCode && tradeSettings.stockCode.length === 6) {
    fetchStockData();
    fetchAccountSettings();
    fetchTradeSetting();
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

/* 均价线范围配置样式 */
.range-config-container {
  display: flex;
  align-items: center;
  gap: 5px;
}

.range-label {
  font-size: 0.9rem;
  font-weight: 500;
  white-space: nowrap;
}

.help-icon {
  margin-left: 4px;
  font-size: 14px;
  color: #909399;
  cursor: help;
}

.label-with-help {
  display: inline-flex;
  align-items: center;
  white-space: nowrap;
}

.buy-label {
  color: #67c23a;
  margin-right: 5px;
}

.sell-label {
  color: #f56c6c;
  margin-left: 5px;
}

.range-symbol {
  font-size: 1.4rem;
  font-weight: bold;
  padding: 0 5px;
}

.minus-symbol {
  color: #67c23a;
}

.plus-symbol {
  color: #f56c6c;
}

.center-text {
  font-weight: bold;
  margin: 0 15px;
  color: #303133;
}

:deep(.range-input) {
  width: 100px !important;
}

:deep(.range-input .el-input__inner) {
  text-align: center;
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
