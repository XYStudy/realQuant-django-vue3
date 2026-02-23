import pandas as pd
import numpy as np
import akshare as ak
import requests
from datetime import datetime, time, timedelta
import os
import warnings
import time as time_module
import json
from decimal import Decimal

warnings.filterwarnings('ignore')

# ==================== 默认配置 ====================
DEFAULT_CONFIG = {
    # ========== 数据配置 ==========
    'data_dir': './data/',              # 📁 本地数据存储目录，用于缓存历史K线数据
    'use_local_file': True,             # 💾 是否优先使用本地文件（True=优先本地，False=每次都从网络获取）
    'local_file_pattern': '{code}.XSHG_5min_{start}_{end}.csv',  # 📄 本地文件命名模板
    
    # ========== 大盘过滤配置 ==========
    'market_filter_enable': True,       # 🛡️ 是否启用大盘过滤（True=启用，False=跳过大盘判断）
    'market_code': '000001',            # 📊 大盘指数代码（000001=上证指数，399001=深证成指）
    
    # ========== 策略核心参数 ==========
    'atr_period': 14,                   # 📐 ATR计算周期（14=14根K线，用于衡量波动率）
    'base_profit_target': 0.010,        # 🎯 基础止盈比例（0.010=1%，动态止盈的最低门槛）
    'trailing_stop_ratio': 0.005,       # 🔒 移动止盈回撤比例（0.005=0.5%，从最高点回撤多少触发止盈）
    'stop_loss': 0.008,                 # ✂️ 硬止损比例（0.008=0.8%，亏损达到此值强制止损）
    'force_close_time': '14:50',        # ⏰ 尾盘强平时间（14:50=14点50分，此时未平仓则强制卖出）
    
    # ========== RSI 阈值配置 ==========
    'rsi_bull_base': 30,                # 🐂 牛市/震荡市RSI超卖阈值（30=RSI<30视为超卖，可买入）
    'rsi_bear_base': 25,                # 🐻 熊市RSI超卖阈值（25=弱势市场要求更严格，RSI<25才买入）
    
    # ========== ATR 倍数配置 ==========
    'atr_mult_low_base': 1.3,           # 📉 低波动时ATR倍数（1.3=波动小时止盈线=ATR×1.3，更容易止盈）
    'atr_mult_mid_base': 1.5,           # 📊 中波动时ATR倍数（1.5=标准倍数，止盈线=ATR×1.5）
    'atr_mult_high_base': 1.8,          # 📈 高波动时ATR倍数（1.8=波动大时止盈线=ATR×1.8，让利润奔跑）
    
    # ========== 时间风控配置 ==========
    'no_buy_time_normal': '14:30',      # ⏳ 正常市场禁买时间（14:30=14点30分后禁止新开仓）
    'no_buy_time_weak': '14:00',        # ⚠️ 弱势市场禁买时间（14:00=弱势时提前到14点禁买，规避尾盘风险）
    
    # ========== 数据过滤配置 ==========
    'min_volume_hand': 100,             # 📦 最小成交量过滤（100=成交量<100手的K线被过滤，避免异常数据）
    
    # ========== 大盘过滤阈值 ==========
    'market_vwap_threshold': -0.005,    # 📊 大盘VWAP偏离阈值（-0.005=大盘低于VWAP 0.5%时警惕）
    'market_rsi_threshold': 45,         # 📊 大盘RSI阈值（45=大盘RSI<45时视为弱势）
    
    # ========== 运行模式配置 ==========
    'realtime_interval': 30,            # ⏱️ 实盘监控刷新间隔（30=每30秒检查一次信号）
}

# ==================== 数据获取器 ====================
class DataFetcher:
    """智能数据获取器：优先本地，不存在则从网络获取"""
    
    def __init__(self, config):
        self.config = config
        self.stock_code = config['stock_code']
        self.market_code = config.get('market_code', '000001')
        self.data_dir = config.get('data_dir', './data/')
        
        os.makedirs(self.data_dir, exist_ok=True)
        
        if self.stock_code.startswith('6'):
            self.stock_secid = f"1.{self.stock_code}"
            self.stock_suffix = "XSHG"
        else:
            self.stock_secid = f"0.{self.stock_code}"
            self.stock_suffix = "XSHE"
        
        self.stock_daily_df = None
        self.stock_5min_df = None
        self.market_5min_df = None
        self.realtime_quote = None
        self.processor = DataProcessor(config)
        
    def get_local_file_path(self, code, start_date, end_date, suffix):
        filename = f"{code}.{suffix}_5min_{start_date}_{end_date}.csv"
        return os.path.join(self.data_dir, filename)
    
    def load_from_local(self, code, start_date, end_date, suffix):
        file_path = self.get_local_file_path(code, start_date, end_date, suffix)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
                return df
            except Exception as e:
                print(f"⚠️ 本地文件读取失败：{e}")
                return None
        return None
    
    def save_to_local(self, df, code, start_date, end_date, suffix):
        file_path = self.get_local_file_path(code, start_date, end_date, suffix)
        try:
            df.to_csv(file_path, encoding='utf_8_sig')
            return True
        except Exception as e:
            print(f"❌ 保存失败：{e}")
            return False
    
    def fetch_from_akshare_5min(self, code, days=60, is_index=False):
        """从 AKShare 获取 5 分钟 K 线数据"""
        try:
            print(f"[INFO] 从 AKShare 获取 {code} 5 分钟数据 (is_index={is_index})...")
            
            if is_index:
                symbol = code
                if code.startswith('sh') or code.startswith('sz'):
                    symbol = code[2:]
                
                print(f"[MultiFactor] 尝试使用 index_zh_a_hist_min_em 获取指数数据：{symbol}")
                try:
                    df = ak.index_zh_a_hist_min_em(symbol=symbol, period="5")
                except Exception as e:
                    print(f"[WARN] index_zh_a_hist_min_em 失败：{e}，尝试使用 stock_zh_a_hist_min_em")
                    df = ak.stock_zh_a_hist_min_em(symbol=code, period="5")
                
                if code.startswith('000001') or symbol == '000001':
                    code = 'sh000001'
            else:
                df = ak.stock_zh_a_hist_min_em(symbol=code, period="5", adjust="qfq")
            
            if not df.empty:
                df = df.rename(columns={
                    '时间': 'datetime',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume_hand',
                    '成交额': 'amount'
                })

                df['datetime'] = pd.to_datetime(df['datetime'])
                
                if not df.empty:
                    print(f"[MultiFactor] DEBUG: Raw data time range: {df['datetime'].min()} to {df['datetime'].max()}")
                    print(f"[MultiFactor] DEBUG: System time: {pd.Timestamp.today()}")
                
                cutoff = pd.Timestamp.today() - pd.Timedelta(days=days)
                print(f"[MultiFactor] DEBUG: Cutoff time: {cutoff}")
                
                df = df[df['datetime'] >= cutoff]
                df.set_index('datetime', inplace=True)
                
                print(f"[SUCCESS] AKShare 获取成功：{len(df)} 根 K 线")
                return df
            else:
                print("[WARN] AKShare 返回空数据")
                return None
        except Exception as e:
            print(f"[ERROR] AKShare 获取失败：{e}")
            return None
    
    def fetch_from_akshare_daily(self, code, days=60):
        """从 AKShare 获取日线数据"""
        try:
            start_date = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime('%Y%m%d')
            end_date = pd.Timestamp.today().strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                   start_date=start_date, end_date=end_date, adjust="qfq")
            
            if len(df) > 0:
                return df
            else:
                return None
        except Exception as e:
            print(f"❌ AKShare 日线获取失败：{e}")
            return None
    
    def get_yesterday_volume(self):
        """获取昨日成交量"""
        if self.stock_daily_df is not None and len(self.stock_daily_df) >= 2:
            return self.stock_daily_df['成交量'].iloc[-2]
        elif self.stock_daily_df is not None and len(self.stock_daily_df) >= 1:
            return self.stock_daily_df['成交量'].iloc[-1]
        return None

    def prepare_data(self):
        """
        准备策略所需的所有数据 (实盘模式)
        ⭐ 修复版：大盘数据统一用 process_market_data 处理
        """
        print("=" * 60, flush=True)
        print("🔧 数据准备", flush=True)
        print("=" * 60, flush=True)
        
        # 1. 获取历史 5 分钟数据（个股）
        if self.stock_5min_df is None:
            self.stock_5min_df = self.fetch_from_akshare_5min(self.stock_code, days=20)
            
            if self.stock_5min_df is not None:
                # 处理个股数据
                yesterday_vol = self.get_yesterday_volume()
                self.stock_5min_df = self.processor.process_stock_data(self.stock_5min_df, yesterday_vol)
                print(f"[MultiFactor] 个股数据获取并处理成功：{len(self.stock_5min_df)} 条", flush=True)
            else:
                print(f"[MultiFactor] 个股数据获取失败", flush=True)
        
        # 2. 获取日线数据
        if self.stock_daily_df is None:
            self.stock_daily_df = self.fetch_from_akshare_daily(self.stock_code, days=60)
            
            if self.stock_daily_df is not None:
                print(f"[MultiFactor] 日线数据获取成功：{len(self.stock_daily_df)} 天", flush=True)
            else:
                print(f"[MultiFactor] 日线数据获取失败", flush=True)
        
        # 3. 获取大盘 5 分钟数据 ⭐ 修复重点
        if self.config.get('market_filter_enable', True):
            if self.market_5min_df is None:
                self.market_5min_df = self.fetch_from_akshare_5min(self.market_code, days=20, is_index=True)
            
            if self.market_5min_df is not None:
                # ⭐ 关键：处理大盘数据并保存返回值
                self.market_5min_df = self.processor.process_market_data(self.market_5min_df)
                
                if self.market_5min_df is not None:
                    print(f"[MultiFactor] 大盘数据 ({self.market_code}) 获取并处理成功，共 {len(self.market_5min_df)} 条", flush=True)
                    print(f"[MultiFactor] 大盘数据列：{self.market_5min_df.columns.tolist()}", flush=True)
                else:
                    print(f"[MultiFactor] 大盘数据 ({self.market_code}) 处理失败", flush=True)
            else:
                print(f"[MultiFactor] 大盘数据 ({self.market_code}) 获取失败或为空", flush=True)
        else:
            print(f"[MultiFactor] 大盘过滤未启用，跳过获取大盘数据", flush=True)
        
        print("=" * 60, flush=True)
    
        return self.stock_5min_df is not None


# ==================== 数据处理与因子计算 ====================
class DataProcessor:
    """数据处理器：计算 V5.6 所需的所有因子"""
    
    def __init__(self, config):
        self.config = config
    
    def process_stock_data(self, df, yesterday_volume=None):
        """处理股票数据，计算所有因子"""
        if df is None or len(df) < 50:
            return None
        
        df = df.copy()
        
        if 'volume_hand' not in df.columns and 'volume' in df.columns:
            df['volume_hand'] = df['volume']
        
        df['volume_hand'] = pd.to_numeric(df['volume_hand'], errors='coerce').fillna(0)
        df = df[df['high'] > 0]
        
        df['volume_shares'] = df['volume_hand'] * 100
        df['amount'] = df['close'] * df['volume_shares']
        df['date'] = df.index.date
        
        # VWAP
        df['cum_amount'] = df.groupby('date')['amount'].cumsum()
        df['cum_volume'] = df.groupby('date')['volume_shares'].cumsum()
        df['vwap'] = df['cum_amount'] / (df['cum_volume'] + 1e-9)
        df['vwap'] = df['vwap'].fillna(df['close'])
        
        # 日内位置
        df['daily_high'] = df.groupby('date')['high'].transform('max')
        df['daily_low'] = df.groupby('date')['low'].transform('min')
        df['intraday_pos'] = (df['close'] - df['daily_low']) / (df['daily_high'] - df['daily_low'] + 1e-9)
        df['intraday_pos'] = df['intraday_pos'].clip(0, 1)
        
        # VWAP 变化率
        df['vwap_change'] = df.groupby('date')['vwap'].pct_change(5)
        
        # 均线
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        
        # RSI (6 和 14 都计算)
        def calc_rsi(series, period):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / (loss + 1e-9)
            return 100 - (100 / (1 + rs))
        
        df['rsi_6'] = calc_rsi(df['close'], 6)
        df['rsi_14'] = calc_rsi(df['close'], 14)
        
        # ATR
        def calc_atr(df, period):
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(period).mean()
        
        df['atr'] = calc_atr(df, self.config.get('atr_period', 14))
        df['atr_pct'] = df['atr'] / df['close']
        
        # 涨跌幅
        df['prev_close'] = df.groupby('date')['close'].shift(1)
        df['prev_close'] = df['prev_close'].ffill()
        df['change_pct'] = (df['close'] - df['prev_close']) / (df['prev_close'] + 1e-9)
        
        # 成交量趋势
        df['vol_increasing'] = (df['volume_hand'].diff() > 0).rolling(5).sum()
        
        # 昨日成交量
        if yesterday_volume:
            df['yesterday_volume'] = yesterday_volume
        else:
            daily_last_vol = df.groupby('date')['volume_hand'].last()
            df['yesterday_volume'] = df['date'].map(daily_last_vol.shift(1))
            df['yesterday_volume'] = df['yesterday_volume'].fillna(df['volume_hand'].iloc[0])
        
        # 日内平均成交量
        df['intraday_avg_vol'] = df.groupby('date')['volume_hand'].transform('mean')
        
        # 动态参数
        df['ma20_slope'] = df['ma20'] - df['ma20'].shift(5)
        df['is_weak_market'] = df['ma20_slope'] < 0
        
        df['rsi6_thresh'] = np.where(df['is_weak_market'], 
                                     self.config.get('rsi_bear_base', 25), 
                                     self.config.get('rsi_bull_base', 30))
        df['rsi14_thresh'] = np.where(df['is_weak_market'], 
                                      self.config.get('rsi_bear_base', 25) + 10, 
                                      self.config.get('rsi_bull_base', 30) + 10)
        
        atr_median = df['atr_pct'].rolling(60).median()
        df['atr_mult'] = np.where(df['atr_pct'] < atr_median * 0.8, 
                                  self.config.get('atr_mult_low_base', 1.3),
                                  np.where(df['atr_pct'] > atr_median * 1.2, 
                                           self.config.get('atr_mult_high_base', 1.8),
                                           self.config.get('atr_mult_mid_base', 1.5)))
        
        df['dynamic_profit_target'] = np.maximum(
            self.config.get('base_profit_target', 0.010), 
            df['atr_pct'] * df['atr_mult']
        )
        
        # 清理 NaN
        df.index.name = 'datetime'
        df = df.dropna().reset_index()
        if 'datetime' not in df.columns and 'index' in df.columns:
            df.rename(columns={'index': 'datetime'}, inplace=True)
             
        if 'datetime' in df.columns:
            df.set_index('datetime', inplace=True)
        
        return df
    
    def process_market_data(self, df):
        """
        ⭐ 专门处理大盘数据（最低 6 条即可）
        与 get_market_condition() 完美配合
        """
        # ========== 1. 数据量检查 ==========
        if df is None or len(df) < 6:  # 最低 6 条（RSI(6) 需求）
            print(f"[WARN] 大盘数据不足 6 条，无法处理")
            return None
        
        df = df.copy()
        
        # ========== 2. 基础清洗 ==========
        if 'volume_hand' not in df.columns and 'volume' in df.columns:
            df['volume_hand'] = df['volume']
    
        df['volume_hand'] = pd.to_numeric(df['volume_hand'], errors='coerce').fillna(0)
        df = df[df['high'] > 0]
        
        # ========== 3. 基础字段 ==========
        df['volume_shares'] = df['volume_hand'] * 100
        df['amount'] = df['close'] * df['volume_shares']
        df['date'] = df.index.date
        
        # ========== 4. VWAP ==========
        df['cum_amount'] = df.groupby('date')['amount'].cumsum()
        df['cum_volume'] = df.groupby('date')['volume_shares'].cumsum()
        df['vwap'] = df['cum_amount'] / (df['cum_volume'] + 1e-9)
        df['vwap'] = df['vwap'].fillna(df['close'])
        
        # ========== 5. 日内位置 ==========
        df['daily_high'] = df.groupby('date')['high'].transform('max')
        df['daily_low'] = df.groupby('date')['low'].transform('min')
        df['intraday_pos'] = (df['close'] - df['daily_low']) / (df['daily_high'] - df['daily_low'] + 1e-9)
        df['intraday_pos'] = df['intraday_pos'].clip(0, 1)
        
        # ========== 6. VWAP 变化率 ==========
        df['vwap_change'] = df.groupby('date')['vwap'].pct_change(5)
        
        # ========== 7. 均线 ==========
        df['ma5'] = df['close'].rolling(5).mean()
        df['ma20'] = df['close'].rolling(20).mean()
        
        # ========== 8. RSI (6 和 14 都计算) ==========
        def calc_rsi(series, period):
            delta = series.diff()
            gain = (delta.where(delta > 0, 0)).rolling(period).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
            rs = gain / (loss + 1e-9)
            return 100 - (100 / (1 + rs))
        
        df['rsi_6'] = calc_rsi(df['close'], 6)
        df['rsi_14'] = calc_rsi(df['close'], 14)
        
            # ========== 9. ATR ==========
        def calc_atr(df, period):
            high_low = df['high'] - df['low']
            high_close = (df['high'] - df['close'].shift()).abs()
            low_close = (df['low'] - df['close'].shift()).abs()
            tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
            return tr.rolling(period).mean()
        
        df['atr'] = calc_atr(df, self.config.get('atr_period', 14))
        df['atr_pct'] = df['atr'] / df['close']
        
        # ========== 10. 涨跌幅 ==========
        df['prev_close'] = df.groupby('date')['close'].shift(1)
        df['prev_close'] = df['prev_close'].ffill()
        df['change_pct'] = (df['close'] - df['prev_close']) / (df['prev_close'] + 1e-9)
        
        # ========== 11. 成交量趋势 ==========
        df['vol_increasing'] = (df['volume_hand'].diff() > 0).rolling(5).sum()
        
        # ========== 12. 昨日成交量（大盘给默认值） ==========
        df['yesterday_volume'] = df['volume_hand'].iloc[0] if len(df) > 0 else 1000000
        
        # ========== 13. 日内平均成交量 ==========
        df['intraday_avg_vol'] = df.groupby('date')['volume_hand'].transform('mean')
        
        # ========== 14. 动态参数 ==========
        df['ma20_slope'] = df['ma20'] - df['ma20'].shift(5)
        df['is_weak_market'] = df['ma20_slope'] < 0
        
        # ========== 15. 清理 NaN（关键修复） ==========
        df.index.name = 'datetime'
        
        # ⭐ 只删除核心字段为 NaN 的行，允许 RSI(14)、MA20 为 NaN
        required_columns = ['close', 'vwap', 'rsi_6', 'change_pct']
        df = df.dropna(subset=required_columns).reset_index()
        
        if 'datetime' not in df.columns and 'index' in df.columns:
            df.rename(columns={'index': 'datetime'}, inplace=True)
             
        if 'datetime' in df.columns:
            df.set_index('datetime', inplace=True)
        
        # ========== 16. 调试输出 ==========
        print(f"[DEBUG] 大盘数据处理成功，最终数据量：{len(df)}")
        print(f"[DEBUG] RSI_6 有效值：{df['rsi_6'].notna().sum()}/{len(df)}")
        print(f"[DEBUG] RSI_14 有效值：{df['rsi_14'].notna().sum()}/{len(df)}")
        print(f"[DEBUG] MA20 有效值：{df['ma20_slope'].notna().sum()}/{len(df)}")
        
        return df


# ==================== 大盘过滤系统（优化版） ====================
class MarketFilter:
    """上证指数过滤系统（实时数据 + 分时段动态RSI）"""
    
    def __init__(self, config):
        self.config = config
    
    def fetch_market_realtime(self):
        """
        ⭐ 核心优化1：实时获取大盘最新5分钟数据
        每次检查信号时调用，确保数据最新
        """
        try:
            market_df = ak.index_zh_a_hist_min_em(symbol="000001", period="5")
            
            if not market_df.empty:
                market_df = market_df.rename(columns={
                    '时间': 'datetime',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume_hand',
                    '成交额': 'amount'
                })
                market_df['datetime'] = pd.to_datetime(market_df['datetime'])
                market_df.set_index('datetime', inplace=True)
                
                # 只保留最近20条（约100分钟）
                market_df = market_df.tail(20)
                
                print(f"[Market] 实时获取大盘数据成功：{len(market_df)}条")
                print(f"[Market] DEBUG: 最近20条大盘数据:\n{market_df}")
                return market_df
        except Exception as e:
            print(f"[WARN] 实时获取大盘数据失败：{e}")
        
        return None
    
    def get_market_condition(self, market_df, current_time):
        """
        ⭐ 核心优化2：分时段动态RSI
        早盘用RSI(6)，10:40后用RSI(14)，保证早盘可交易
        """
        # ========== 1. 数据质量检查 ==========
        if market_df is None or len(market_df) < 6:
            print("[WARN] 大盘数据不足，使用降级策略")
            return 'normal', 0.5
        
        # ========== 2. 获取已完成的K线（避免数据漂移）==========
        try:
            completed_time = current_time.replace(
                minute=(current_time.minute // 5) * 5,
                second=0,
                microsecond=0
            ) - timedelta(minutes=5)
            
            market_row = market_df.loc[:completed_time].iloc[-1]
            
            kline_age = (current_time - market_row.name).total_seconds() / 60
            if kline_age > 10:
                print(f"[WARN] 大盘数据过旧 ({kline_age:.1f}分钟)，使用降级策略")
                return 'normal', 0.5
                
        except Exception as e:
            print(f"[WARN] 获取大盘K线失败：{e}，使用降级策略")
            return 'normal', 0.5
        
        # ========== 3. 计算可用K线数量 ==========
        available_bars = len(market_df.loc[:completed_time])
        
        # ========== 4. 分时段动态RSI（核心优化）==========
        if available_bars >= 14:
            # 10:40之后：用RSI(14) 更稳定
            market_rsi = market_row.get('rsi_14', 50)
            rsi_type = 'RSI(14)'
            rsi_weights = {'over_bought': 60, 'over_sold': 40}
            is_early_market = False
        elif available_bars >= 6:
            # 09:55-10:40：用RSI(6) 保证早盘交易
            market_rsi = market_row.get('rsi_6', 50)
            rsi_type = 'RSI(6)'
            rsi_weights = {'over_bought': 70, 'over_sold': 30}
            is_early_market = True
        else:
            # 09:30-09:55：数据不足，降低RSI权重
            market_rsi = market_row.get('rsi_6', 50)
            rsi_type = 'RSI(6)*'
            rsi_weights = {'over_bought': 75, 'over_sold': 25}
            is_early_market = True
        
        # ========== 5. 多维度评分 ==========
        score = 0.0
        
        # --- 5.1 VWAP 偏离 (早盘权重更高) ---
        vwap = market_row.get('vwap', market_row['close'])
        if vwap > 0:
            market_vwap_dev = (market_row['close'] - vwap) / vwap
        else:
            market_vwap_dev = 0
        
        if is_early_market:
            # 早盘：提高VWAP权重（RSI数据不足）
            if market_vwap_dev > 0.005: score += 0.40
            elif market_vwap_dev > 0: score += 0.20
            elif market_vwap_dev < -0.005: score -= 0.40
            else: score -= 0.20
            vwap_weight = 0.40
        else:
            # 正常：标准权重
            if market_vwap_dev > 0.005: score += 0.30
            elif market_vwap_dev > 0: score += 0.15
            elif market_vwap_dev < -0.005: score -= 0.30
            else: score -= 0.15
            vwap_weight = 0.30
        
        # --- 5.2 RSI 评分 (动态权重) ---
        rsi_weight = 0.25 if available_bars >= 14 else 0.15
        
        if market_rsi > rsi_weights['over_bought']:
            score += rsi_weight
        elif market_rsi > 50:
            score += rsi_weight * 0.5
        elif market_rsi < rsi_weights['over_sold']:
            score -= rsi_weight
        elif market_rsi < 50:
            score -= rsi_weight * 0.5
        
        # --- 5.3 MA20 趋势 (25%) ---
        market_ma20_slope = market_row.get('ma20_slope', 0)
        if pd.isna(market_ma20_slope):
            market_ma20_slope = 0
        
        ma20_normalized = market_ma20_slope / market_row['close'] if market_row['close'] > 0 else 0
        
        if ma20_normalized > 0.002: score += 0.25
        elif ma20_normalized > 0: score += 0.10
        elif ma20_normalized < -0.002: score -= 0.25
        else: score -= 0.10
        
        # --- 5.4 大盘涨跌幅 (20%) ---
        market_change_pct = market_row.get('change_pct', 0)
        if pd.isna(market_change_pct):
            market_change_pct = 0
        
        if market_change_pct > 0.01: score += 0.20
        elif market_change_pct > 0.005: score += 0.10
        elif market_change_pct < -0.01: score -= 0.20
        elif market_change_pct < -0.005: score -= 0.10
        
        score = max(-1.0, min(1.0, score))
        
        # ========== 6. 判定等级 ==========
        if score >= 0.4: return 'strong', score
        elif score >= 0.1: return 'normal', score
        elif score >= -0.2: return 'weak', score
        else: return 'danger', score
    
    def check(self, market_df, current_time, stock_is_weak):
        """
        大盘过滤检查（早盘优化版）
        """
        if market_df is not None:
             print(f"[MultiFactor] DEBUG: market_df shape: {market_df.shape}\n{market_df.tail(2)}")
        else:
             print("[MultiFactor] DEBUG: market_df is None")

        if not self.config.get('market_filter_enable', True) or market_df is None:
            return True, 0.55, "大盘过滤未启用"
        
        # 检查是否早盘
        is_early_market = current_time.hour < 10 or (current_time.hour == 10 and current_time.minute < 40)
        
        condition, score = self.get_market_condition(market_df, current_time)
        
        if condition == 'danger':
            return False, 0, f"🔴 大盘危险 (评分={score:.2f})"
        
        elif condition == 'weak':
            if is_early_market:
                return True, 0.70, f"🟡 早盘弱势 (评分={score:.2f})"
            else:
                return True, 0.65, f"🟡 大盘弱势 (评分={score:.2f})"
        
        elif condition == 'normal':
            if is_early_market:
                threshold = 0.60 if stock_is_weak else 0.55
                return True, threshold, f"🟢 早盘正常 (评分={score:.2f})"
            else:
                threshold = 0.60 if stock_is_weak else 0.55
                return True, threshold, f"🟢 大盘正常 (评分={score:.2f})"
        
        else:  # strong
            return True, 0.50, f"🟢 大盘强势 (评分={score:.2f})"


# ==================== V5.6 评分系统 ====================
class V56Scorer:
    """V5.6 策略评分系统"""
    
    def __init__(self, config):
        self.config = config
    
    def score_vwap(self, row):
        vwap_dev = (row['close'] - row['vwap']) / (row['vwap'] + 1e-9)
        if vwap_dev < -0.02: return 0.25
        elif vwap_dev < -0.01: return 0.20
        elif vwap_dev < 0: return 0.10
        return 0.0
    
    def score_intraday_position(self, row):
        pos = row['intraday_pos']
        if pos < 0.15: return 0.20
        elif pos < 0.30: return 0.15
        elif pos < 0.50: return 0.05
        return 0.0
    
    def score_vwap_change(self, row):
        vc = row.get('vwap_change', 0)
        if pd.isna(vc): return 0.05
        if -0.02 < vc < -0.005: return 0.15
        elif abs(vc) < 0.002: return 0.10
        return 0.0
    
    def score_trend(self, row):
        if row['close'] > row['ma20']: return 0.15
        elif row['close'] > row['ma5']: return 0.08
        return 0.0
    
    def score_rsi(self, row):
        rsi6 = row.get('rsi_6', 50)
        rsi14 = row.get('rsi_14', 50)
        t6 = row.get('rsi6_thresh', 30)
        t14 = row.get('rsi14_thresh', 40)
        
        if rsi6 < t6 and rsi14 < t14: return 0.15
        elif rsi6 < t6 or rsi14 < t14: return 0.08
        return 0.0
    
    def score_volume(self, row):
        score = 0.0
        current_vol = row.get('volume_hand', 0)
        yesterday_vol = row.get('yesterday_volume', current_vol)
        
        if yesterday_vol and yesterday_vol > 0:
            vol_ratio = current_vol / yesterday_vol
            if vol_ratio > 2.0: score += 0.05
            elif vol_ratio > 1.5: score += 0.04
            elif vol_ratio > 1.2: score += 0.03
            else: score += 0.02
            
            change_pct = row.get('change_pct', 0)
            if vol_ratio > 1.5 and change_pct < -0.02:
                score += 0.02
        else:
            score += 0.02
        
        intra_avg = row.get('intraday_avg_vol', current_vol)
        if intra_avg and intra_avg > 0:
            intra_ratio = current_vol / intra_avg
            if intra_ratio > 1.5: score += 0.03
            elif intra_ratio > 1.0: score += 0.02
            else: score += 0.01
        
        vol_inc = row.get('vol_increasing', 0)
        if vol_inc >= 4: score += 0.02
        elif vol_inc >= 3: score += 0.01
        
        return min(score, 0.15)
    
    def calculate_total(self, row):
        """计算综合评分"""
        return (self.score_vwap(row) + 
                self.score_intraday_position(row) + 
                self.score_vwap_change(row) + 
                self.score_trend(row) + 
                self.score_rsi(row) + 
                self.score_volume(row))


# ==================== 策略服务 ====================
class MultiFactorStrategy:
    """
    多因子策略服务
    维护每个股票的策略状态
    """
    _instances = {}
    
    def __init__(self, stock_code, config=None):
        self.stock_code = stock_code
        self.config = config if config else DEFAULT_CONFIG.copy()
        
        self.config['stock_code'] = stock_code
        
        if config and 'market_filter_enable' in config:
            self.config['market_filter_enable'] = config['market_filter_enable']
        
        self.config['stock_name'] = '未知'
        
        self.fetcher = DataFetcher(self.config)
        self.processor = DataProcessor(self.config)
        self.scorer = V56Scorer(self.config)
        self.market_filter = MarketFilter(self.config)
        
        self.is_initialized = False
        self.last_update_time = None

    @classmethod
    def get_instance(cls, stock_code):
        if stock_code not in cls._instances:
            cls._instances[stock_code] = cls(stock_code)
        return cls._instances[stock_code]
    
    def check_signal(self, stock_data, setting):
        """
        检查交易信号
        返回：(should_trade, trade_type, reason, extra_info)
        """
        try:
            if setting:
                if 'market_filter_enable' in setting:
                    self.config['market_filter_enable'] = setting['market_filter_enable']
            
            now = datetime.now()
            if not self.is_initialized or (self.last_update_time and self.last_update_time.date() != now.date()):
                print(f"[MultiFactor] 初始化数据 {self.stock_code}...", flush=True)
                print(f"[MultiFactor] DEBUG: market_filter_enable={self.config.get('market_filter_enable')}", flush=True)
                success = self.fetcher.prepare_data()
                if success:
                    self.is_initialized = True
                    self.last_update_time = now
                    yesterday_vol = self.fetcher.get_yesterday_volume()
                    self.processor.process_stock_data(self.fetcher.stock_5min_df, yesterday_vol)
                    if self.fetcher.market_5min_df is not None:
                        self.fetcher.market_5min_df = self.processor.process_market_data(self.fetcher.market_5min_df)
                else:
                    return False, None, "数据初始化失败", None
            
            quote = {
                'open': stock_data.get('open', stock_data['current_price']),
                'high': stock_data['high'],
                'low': stock_data['low'],
                'current': stock_data['current_price'],
                'volume_hand': stock_data['volume'],
                'amount': stock_data.get('amount', 0),
                'timestamp': pd.to_datetime(stock_data['timestamp'])
            }
            
            if quote['amount'] == 0 and quote['volume_hand'] > 0:
                quote['amount'] = quote['current'] * quote['volume_hand'] * 100

            current_row = pd.DataFrame([{
                'open': quote['open'],
                'high': quote['high'],
                'low': quote['low'],
                'close': quote['current'],
                'volume_hand': quote['volume_hand'],
                'amount': quote['amount']
            }], index=[quote['timestamp']])
            
            df = pd.concat([self.fetcher.stock_5min_df, current_row])
            df = df.drop_duplicates(keep='last').sort_index()
            
            yesterday_vol = self.fetcher.get_yesterday_volume()
            processed_df = self.processor.process_stock_data(df, yesterday_vol)
            
            if processed_df is None or len(processed_df) == 0:
                return False, None, "数据处理后为空", None
            
            current_data = processed_df.iloc[-1]
            
            score = self.scorer.calculate_total(current_data)
            
            # ⭐ 核心优化：每次检查信号时更新大盘数据
            if self.config.get('market_filter_enable', True):
                market_df = self.market_filter.fetch_market_realtime()
                if market_df is not None:
                    market_df = self.processor.process_market_data(market_df)
            else:
                market_df = None
            
            allow_trade, threshold, market_reason = self.market_filter.check(
                market_df, 
                now, 
                current_data.get('is_weak_market', False)
            )
            
            if not self.config.get('market_filter_enable', True):
                allow_trade = True
                if "大盘危险" in market_reason:
                    market_reason = f"{market_reason} (已忽略)"
            
            extra_info = {
                'score': round(float(score), 2),
                'threshold': round(float(threshold), 2),
                'market_reason': market_reason,
                'is_weak_market': bool(current_data.get('is_weak_market', False))
            }
            
            print(f"[MultiFactor] {self.stock_code} Score: {score:.2f} Threshold: {threshold} Reason: {market_reason} Allow: {allow_trade}")
            
            if not allow_trade:
                return False, None, f"大盘过滤：{market_reason}", extra_info
            
            pending_loop_type = setting.get('pending_loop_type')
            
            if not pending_loop_type:
                if score >= threshold:
                    return True, 'buy', f"多因子评分买入 (Score={score:.2f})", extra_info
                else:
                    print(f"[MultiFactor] 分数不足：{score:.2f} < {threshold}")
                    return False, None, f"分数不足 (Score={score:.2f})", extra_info
            
            elif pending_loop_type == 'buy_first':
                buy_price = float(setting.get('pending_price', 0))
                if buy_price > 0:
                    current_price = float(stock_data['current_price'])
                    profit_pct = (current_price - buy_price) / buy_price
                    
                    target = current_data.get('dynamic_profit_target', self.config['base_profit_target'])
                    extra_info['profit_pct'] = round(profit_pct, 4)
                    extra_info['target_profit'] = round(target, 4)
                    
                    if profit_pct >= target:
                        return True, 'sell', f"多因子止盈 (收益{profit_pct:.2%})", extra_info
                    
                    if profit_pct <= -self.config['stop_loss']:
                        return True, 'sell', f"多因子止损 (收益{profit_pct:.2%})", extra_info
                    
                    if now.time() >= datetime.strptime(self.config['force_close_time'], '%H:%M').time():
                        return True, 'sell', "尾盘强平", extra_info
            
            return False, None, "无信号", extra_info
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            return False, None, f"策略错误：{e}", None