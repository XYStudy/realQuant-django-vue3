<template>
  <div ref="chartRef" class="stock-chart-container"></div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, watch, defineProps, defineEmits } from 'vue';
import * as echarts from 'echarts';

// 定义组件属性
const props = defineProps({
  chartData: {
    type: Object,
    default: () => ({
      time: [],
      price: [],
      average: [],
      price_diff_percent: []
    })
  },
  realtimeData: {
    type: Object,
    default: () => ({
      currentPrice: 0,
      averagePrice: 0,
      priceDiff: 0,
      highPrice: 0,
      lowPrice: 0
    })
  }
});

// 定义事件
const emit = defineEmits(['chart-ready']);

// 图表实例
let chartInstance = null;
const chartRef = ref(null);

// 初始化图表
const initChart = () => {
  if (!chartRef.value) return;
  
  chartInstance = echarts.init(chartRef.value);
  
  const option = {
    backgroundColor: '#000000',
    tooltip: {
      trigger: 'axis',
      formatter: function(params) {
        let result = params[0].axisValue + '<br/>';
        params.forEach(function(item) {
          result += item.marker + item.seriesName + ': ' + item.data + '<br/>';
        });
        return result;
      },
      textStyle: {
        color: '#ffffff',
      },
      backgroundColor: 'rgba(0, 0, 0, 0.8)',
      borderColor: '#666666',
    },
    legend: {
      data: ['当前价格', '均价'],
      top: 10,
      left: 'center',
      textStyle: {
        color: '#ffffff',
      },
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      top: 40,
      containLabel: true,
      backgroundColor: '#000000',
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: props.chartData.time,
      axisLine: {
        lineStyle: {
          color: '#444444',
        },
      },
      axisLabel: {
        color: '#ffffff',
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#333333',
          type: 'dashed',
        },
      },
    },
    yAxis: {
      type: 'value',
      axisLine: {
        lineStyle: {
          color: '#444444',
        },
      },
      axisLabel: {
        color: '#ffffff',
        formatter: function(value) {
          if (value == null || isNaN(value)) return '0.00';
          return Number(value).toFixed(2);
        },
      },
      splitLine: {
        show: true,
        lineStyle: {
          color: '#8B0000',
        },
      },
      splitNumber: 10,
    },
    series: [
      {
        name: '当前价格',
        type: 'line',
        data: props.chartData.price,
        smooth: false,
        symbol: 'none',
        lineStyle: {
          color: '#ffffff',
          width: 1,
        },
      },
      {
        name: '均价',
        type: 'line',
        data: props.chartData.average,
        smooth: true,
        symbol: 'none',
        lineStyle: {
          color: '#FFFF00',
          width: 1,
        },
      },
    ],
  };
  
  chartInstance.setOption(option);
  emit('chart-ready', chartInstance);
};

// 动态更新格子的步长算法
const getGridStep = (high, low) => {
  const range = high - low;
  if (range <= 0) return 0.01;

  // 尝试不同格子数（6～8），选最合适的 nice step
  const candidates = [];
  for (let n = 6; n <= 8; n++) {
    const step = range / n;
    candidates.push(step);
  }
  const ideal = Math.min(...candidates); // 取最小步长（最多格子）

  // 美化序列（包含0.06）
  const nice = [0.01, 0.02, 0.05, 0.06, 0.08, 0.1, 0.2, 0.25, 0.5, 1, 2, 5, 10];
  for (let v of nice) {
    if (v >= ideal * 0.9) { // 允许90%容差
      return v;
    }
  }
  return ideal;
};

// 更新图表
const updateChart = () => {
  // 计算Y轴范围，使用专业股票软件的刻度间距算法
  const allPrices = [...props.chartData.price, ...props.chartData.average];
  
  // 获取当日最高价和最低价（优先使用实时数据，否则使用图表数据）
  let pMax = props.realtimeData.highPrice > 0 ? props.realtimeData.highPrice : Math.max(...allPrices);
  let pMin = props.realtimeData.lowPrice > 0 ? props.realtimeData.lowPrice : Math.min(...allPrices);
  
  // 如果没有有效数据，使用图表数据
  if (!pMax || pMax === 0) pMax = Math.max(...allPrices);
  if (!pMin || pMin === 0) pMin = Math.min(...allPrices);
  
  // 确保范围有效
  if (pMax === pMin) {
    const range = pMax * 0.01 || 0.05;
    pMax += range;
    pMin -= range;
  }
  
  // 使用新的步长算法
  const niceInterval = getGridStep(pMax, pMin);
  
  // 重新计算坐标轴范围
  // 以niceInterval为间距，找到能覆盖[pMin, pMax]的最小整数倍范围
  const yMin = Math.floor(pMin / niceInterval) * niceInterval;
  const yMax = Math.ceil(pMax / niceInterval) * niceInterval;
  
  // 应用到图表
  chartInstance.setOption({
    xAxis: {
      data: props.chartData.time,
    },
    yAxis: {
      min: Math.max(0, yMin),  // 价格不能为负
      max: yMax,
      splitNumber: Math.round((yMax - yMin) / niceInterval),
      interval: niceInterval,
    },
    series: [
      {
        data: props.chartData.price,
      },
      {
        data: props.chartData.average,
      },
    ],
  });
};

// 监听图表数据变化，更新图表
watch(
  () => props.chartData,
  () => {
    updateChart();
  },
  { deep: true }
);

// 监听实时数据变化，更新图表
watch(
  () => props.realtimeData,
  () => {
    updateChart();
  },
  { deep: true }
);

// 窗口大小变化时，调整图表大小
const handleResize = () => {
  chartInstance?.resize();
};

// 组件挂载时初始化图表
onMounted(() => {
  initChart();
  window.addEventListener('resize', handleResize);
});

// 组件卸载时销毁图表实例
onUnmounted(() => {
  chartInstance?.dispose();
  window.removeEventListener('resize', handleResize);
});

// 暴露方法给父组件
const getChartInstance = () => chartInstance;

defineExpose({
  initChart,
  updateChart,
  getChartInstance
});
</script>

<style scoped>
.stock-chart-container {
  width: 100%;
  height: 100%;
  min-height: 400px;
}
</style>
