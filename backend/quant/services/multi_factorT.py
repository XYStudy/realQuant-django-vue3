import pandas as pd
import numpy as np
import akshare as ak
import requests
from datetime import datetime, time, timedelta
import os
import warnings
import time as time_module
import json

warnings.filterwarnings('ignore')

# ==================== 配置区 ====================
CONFIG = {
    # 股票配置
    'stock_code': '603069',  # 6 位代码
    'stock_name': '海汽集团',
    
    # 数据配置
    'data_dir': './data/',  # 本地数据存储目录
    'use_local_file': True,  # 优先使用本地文件
    'local_file_pattern': '{code}.XSHG_5min_{start}_{end}.csv',
    
    # 大盘过滤配置
    'market_filter_enable': True,
    'market_code': '000001',  # 上证指数
    
    # 策略参数
    'atr_period': 14,
    'base_profit_target': 0.010,
    'trailing_stop_ratio': 0.005,
    'stop_loss': 0.008,
    'force_close_time': '14:50',
    'rsi_bull_base': 30,
    'rsi_bear_base': 25,
    'atr_mult_low_base': 1.3,
    'atr_mult_mid_base': 1.5,
    'atr_mult_high_base': 1.8,
    'no_buy_time_normal': '14:30',
    'no_buy_time_weak': '14:00',
    't_position_amount': 30000,
    'min_volume_hand': 100,
    
    # 大盘过滤阈值
    'market_vwap_threshold': -0.005,
    'market_rsi_threshold': 45,
    
    # 运行模式
    'mode': 'backtest',  # 'backtest' 或 'realtime'
    'backtest_start_date': '2025-04-25',
    'backtest_end_date': '2025-06-17',
    'realtime_interval': 30,  # 秒
}

# ==================== 数据获取器 ====================
class DataFetcher:
    """智能数据获取器：优先本地，不存在则从网络获取"""
    
    def __init__(self, config):
        self.config = config
        self.stock_code = config['stock_code']
        self.market_code = config['market_code']
        self.data_dir = config['data_dir']
        
        # 创建数据目录
        os.makedirs(self.data_dir, exist_ok=True)
        
        # 确定市场类型
        if self.stock_code.startswith('6'):
            self.stock_secid = f"1.{self.stock_code}"
            self.stock_suffix = "XSHG"
        else:
            self.stock_secid = f"0.{self.stock_code}"
            self.stock_suffix = "XSHE"
        
        if self.market_code.startswith('6'):
            self.market_secid = f"1.{self.market_code}"
        else:
            self.market_secid = f"0.{self.market_code}"
        
        # 数据缓存
        self.stock_daily_df = None
        self.stock_5min_df = None
        self.market_5min_df = None
        self.realtime_quote = None
        
    def get_local_file_path(self, code, start_date, end_date, suffix):
        """生成本地文件路径"""
        filename = f"{code}.{suffix}_5min_{start_date}_{end_date}.csv"
        return os.path.join(self.data_dir, filename)
    
    def load_from_local(self, code, start_date, end_date, suffix):
        """从本地文件加载数据"""
        file_path = self.get_local_file_path(code, start_date, end_date, suffix)
        if os.path.exists(file_path):
            try:
                df = pd.read_csv(file_path, index_col='datetime', parse_dates=True)
                print(f"✅ 本地加载：{os.path.basename(file_path)} ({len(df)} 行)")
                return df
            except Exception as e:
                print(f"⚠️ 本地文件读取失败：{e}")
                return None
        return None
    
    def save_to_local(self, df, code, start_date, end_date, suffix):
        """保存数据到本地"""
        file_path = self.get_local_file_path(code, start_date, end_date, suffix)
        try:
            df.to_csv(file_path, encoding='utf_8_sig')
            print(f"💾 已保存：{os.path.basename(file_path)}")
            return True
        except Exception as e:
            print(f"❌ 保存失败：{e}")
            return False
    
    def fetch_from_akshare_5min(self, code, days=60):
        """从 AKShare 获取 5 分钟 K 线数据"""
        try:
            print(f"📥 从 AKShare 获取 {code} 5 分钟数据...")
            df = ak.stock_zh_a_hist_min_em(symbol=code, period="5", adjust="qfq")
            
            if not df.empty:
                # 标准化列名
                df = df.rename(columns={
                    '时间': 'datetime',
                    '开盘': 'open',
                    '最高': 'high',
                    '最低': 'low',
                    '收盘': 'close',
                    '成交量': 'volume_hand',
                    '成交额': 'amount'
                })

                # 转换为 datetime
                df['datetime'] = pd.to_datetime(df['datetime'])
                
                # 限制天数
                cutoff = pd.Timestamp.today() - pd.Timedelta(days=days)
                df = df[df['datetime'] >= cutoff]
                
                df.set_index('datetime', inplace=True)
                
                print(f"✅ AKShare 获取成功：{len(df)} 根 K 线")
                return df
            else:
                print("⚠️ AKShare 返回空数据")
                return None
        except Exception as e:
            print(f"❌ AKShare 获取失败：{e}")
            return None
    
    def fetch_from_akshare_daily(self, code, days=60):
        """从 AKShare 获取日线数据（用于昨日成交量）"""
        try:
            print(f"📥 从 AKShare 获取 {code} 日线数据...")
            start_date = (pd.Timestamp.today() - pd.Timedelta(days=days)).strftime('%Y%m%d')
            end_date = pd.Timestamp.today().strftime('%Y%m%d')
            
            df = ak.stock_zh_a_hist(symbol=code, period="daily", 
                                   start_date=start_date, end_date=end_date, adjust="qfq")
            
            if len(df) > 0:
                print(f"✅ AKShare 日线获取成功：{len(df)} 天")
                return df
            else:
                return None
        except Exception as e:
            print(f"❌ AKShare 日线获取失败：{e}")
            return None
    
    def fetch_from_eastmoney_realtime(self, secid):
        """从东方财富获取实时数据"""
        try:
            url = "https://push2.eastmoney.com/api/qt/stock/get"
            params = {
                "secid": secid,
                "fields": "f43,f44,f45,f46,f47,f48,f60"
            }
            
            resp = requests.get(url, params=params, timeout=5)
            data = resp.json()
            quote = data.get("data", {})
            
            if quote:
                f43 = quote.get("f43", 0)
                f44 = quote.get("f44", 0)
                f45 = quote.get("f45", 0)
                f46 = quote.get("f46", 0)
                f47 = quote.get("f47", 0)
                f48 = quote.get("f48", 0)
                f60 = quote.get("f60", 0)
                
                return {
                    'current': f43 / 100,
                    'high': f44 / 100,
                    'low': f45 / 100,
                    'open': f46 / 100,
                    'prev_close': f60 / 100,
                    'volume_hand': f47,
                    'amount': f48,
                    'change_pct': (f43 - f60) / f60 if f60 > 0 else 0,
                    'timestamp': datetime.now()
                }
            return None
        except Exception as e:
            print(f"❌ 东方财富实时数据获取失败：{e}")
            return None
    
    def prepare_data(self, mode='backtest', start_date=None, end_date=None):
        """
        准备策略所需的所有数据
        优先本地文件，不存在则从网络获取
        """
        print("=" * 60)
        print("🔧 数据准备")
        print("=" * 60)
        
        if mode == 'backtest':
            # ========== 回测模式 ==========
            if start_date is None:
                start_date = self.config['backtest_start_date']
            if end_date is None:
                end_date = self.config['backtest_end_date']
            
            # 1. 加载股票 5 分钟数据
            if self.config['use_local_file']:
                self.stock_5min_df = self.load_from_local(
                    self.stock_code, start_date, end_date, self.stock_suffix)
            
            if self.stock_5min_df is None:
                print("⚠️ 本地文件不存在，从 AKShare 下载...")
                self.stock_5min_df = self.fetch_from_akshare_5min(self.stock_code, days=90)
                
                if self.stock_5min_df is not None:
                    # 过滤日期范围
                    self.stock_5min_df = self.stock_5min_df[
                        (self.stock_5min_df.index.date >= pd.to_datetime(start_date).date()) &
                        (self.stock_5min_df.index.date <= pd.to_datetime(end_date).date())
                    ]
                    # 保存到本地
                    self.save_to_local(self.stock_5min_df, self.stock_code, 
                                      start_date, end_date, self.stock_suffix)
            
            # 2. 加载股票日线数据（用于昨日成交量）
            self.stock_daily_df = self.fetch_from_akshare_daily(self.stock_code, days=60)
            
            # 3. 加载大盘数据
            if self.config['market_filter_enable']:
                if self.config['use_local_file']:
                    self.market_5min_df = self.load_from_local(
                        self.market_code, start_date, end_date, "XSHG")
                
                if self.market_5min_df is None:
                    print("⚠️ 大盘本地文件不存在，从 AKShare 下载...")
                    self.market_5min_df = self.fetch_from_akshare_5min(self.market_code, days=90)
                    
                    if self.market_5min_df is not None:
                        self.market_5min_df = self.market_5min_df[
                            (self.market_5min_df.index.date >= pd.to_datetime(start_date).date()) &
                            (self.market_5min_df.index.date <= pd.to_datetime(end_date).date())
                        ]
                        self.save_to_local(self.market_5min_df, self.market_code,
                                         start_date, end_date, "XSHG")
            
            return self.stock_5min_df is not None
            
        else:
            # ========== 实盘模式 ==========
            # 1. 获取历史 5 分钟数据（用于计算指标）
            self.stock_5min_df = self.fetch_from_akshare_5min(self.stock_code, days=5)
            
            # 2. 获取日线数据
            self.stock_daily_df = self.fetch_from_akshare_daily(self.stock_code, days=60)
            
            # 3. 获取大盘 5 分钟数据
            if self.config['market_filter_enable']:
                self.market_5min_df = self.fetch_from_akshare_5min(self.market_code, days=5)
            
            # 4. 获取实时数据
            self.realtime_quote = self.fetch_from_eastmoney_realtime(self.stock_secid)
            
            return self.stock_5min_df is not None and self.realtime_quote is not None
    
    def get_yesterday_volume(self):
        """获取昨日成交量"""
        if self.stock_daily_df is not None and len(self.stock_daily_df) >= 2:
            return self.stock_daily_df['成交量'].iloc[-2]
        elif self.stock_daily_df is not None and len(self.stock_daily_df) >= 1:
            return self.stock_daily_df['成交量'].iloc[-1]
        return None
    
    def get_realtime_quote(self):
        """获取实时数据（实盘模式）"""
        self.realtime_quote = self.fetch_from_eastmoney_realtime(self.stock_secid)
        return self.realtime_quote


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
        
        # 基础清洗
        if 'volume_hand' not in df.columns and 'volume' in df.columns:
            df['volume_hand'] = df['volume']
        
        df = df[df['volume_hand'] > self.config['min_volume_hand']]
        df = df[df['high'] > 0]
        
        # 基础字段
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
        
        # RSI
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
        
        df['atr'] = calc_atr(df, self.config['atr_period'])
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
                                     self.config['rsi_bear_base'], 
                                     self.config['rsi_bull_base'])
        df['rsi14_thresh'] = np.where(df['is_weak_market'], 
                                      self.config['rsi_bear_base'] + 10, 
                                      self.config['rsi_bull_base'] + 10)
        
        atr_median = df['atr_pct'].rolling(60).median()
        df['atr_mult'] = np.where(df['atr_pct'] < atr_median * 0.8, 
                                  self.config['atr_mult_low_base'],
                                  np.where(df['atr_pct'] > atr_median * 1.2, 
                                           self.config['atr_mult_high_base'],
                                           self.config['atr_mult_mid_base']))
        
        df['dynamic_profit_target'] = np.maximum(
            self.config['base_profit_target'], 
            df['atr_pct'] * df['atr_mult']
        )
        
        # 清理 NaN
        df = df.dropna().reset_index()
        df.set_index('datetime', inplace=True)
        
        return df
    
    def process_market_data(self, df):
        """处理大盘数据"""
        return self.process_stock_data(df)


# ==================== 大盘过滤系统 ====================
class MarketFilter:
    """上证指数过滤系统"""
    
    def __init__(self, config):
        self.config = config
    
    def get_market_condition(self, market_df, current_time):
        """
        判断当前大盘状态
        返回：'strong' / 'normal' / 'weak' / 'danger'
        """
        if market_df is None:
            return 'normal', 0.5
        
        try:
            market_row = market_df.loc[:current_time].iloc[-1]
        except:
            return 'normal', 0.5
        
        # 1. 大盘 VWAP 偏离
        market_vwap_dev = (market_row['close'] - market_row['vwap']) / market_row['vwap']
        
        # 2. 大盘 RSI
        market_rsi = market_row.get('rsi_6', 50)
        
        # 3. 大盘趋势
        market_ma20_slope = market_row['ma20'] - market_row['ma20'].shift(5)
        if pd.isna(market_ma20_slope):
            market_ma20_slope = 0
        
        # 4. 综合评分
        score = 0.0
        
        if market_vwap_dev > 0.005: score += 0.4
        elif market_vwap_dev > 0: score += 0.2
        elif market_vwap_dev < -0.005: score -= 0.4
        else: score -= 0.2
        
        if market_rsi > 55: score += 0.3
        elif market_rsi > 45: score += 0.1
        elif market_rsi < 35: score -= 0.3
        else: score -= 0.1
        
        if market_ma20_slope > 0: score += 0.3
        else: score -= 0.3
        
        # 判定等级
        if score >= 0.5: return 'strong', score
        elif score >= 0.2: return 'normal', score
        elif score >= -0.2: return 'weak', score
        else: return 'danger', score
    
    def check(self, market_df, current_time, stock_is_weak):
        """
        大盘过滤检查
        返回：(是否允许交易，建议阈值，原因)
        """
        if not self.config['market_filter_enable'] or market_df is None:
            return True, 0.55, "大盘过滤未启用"
        
        condition, score = self.get_market_condition(market_df, current_time)
        
        if condition == 'danger':
            return False, 0, f"大盘危险 (评分={score:.2f})"
        elif condition == 'weak':
            return True, 0.65, f"大盘弱势 (评分={score:.2f})"
        elif condition == 'normal':
            threshold = 0.55
            return True, threshold, f"大盘正常 (评分={score:.2f})"
        else:  # strong
            return True, 0.50, f"大盘强势 (评分={score:.2f})"


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
        
        # 量比 (5%)
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
        
        # 日内相对量能 (3%)
        intra_avg = row.get('intraday_avg_vol', current_vol)
        if intra_avg and intra_avg > 0:
            intra_ratio = current_vol / intra_avg
            if intra_ratio > 1.5: score += 0.03
            elif intra_ratio > 1.0: score += 0.02
            else: score += 0.01
        
        # 成交量趋势 (2%)
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


# ==================== 回测引擎 ====================
class Backtester:
    """V5.6 回测引擎"""
    
    def __init__(self, config, scorer, market_filter):
        self.config = config
        self.scorer = scorer
        self.market_filter = market_filter
    
    def run(self, stock_df, market_df):
        """运行回测"""
        print("\n" + "=" * 60)
        print("🚀 开始运行 V5.6 回测")
        print("=" * 60)
        
        trades = []
        position = None
        total_profit = 0
        capital = self.config['t_position_amount']
        capital_curve = [capital]
        skipped_by_market = 0
        
        force_close_time = datetime.strptime(self.config['force_close_time'], '%H:%M').time()
        
        for i, row in stock_df.iterrows():
            current_time = i.time()
            current_price = row['close']
            
            # 大盘过滤检查
            allow_trade, threshold, market_reason = self.market_filter.check(
                market_df, i, row.get('is_weak_market', False))
            
            # 卖出逻辑
            if position:
                profit_pct = (current_price - position['buy_price']) / position['buy_price']
                if current_price > position['highest_price']:
                    position['highest_price'] = current_price
                
                should_sell = False
                reason = ""
                
                if current_time >= force_close_time:
                    should_sell = True
                    reason = "尾盘强平"
                elif profit_pct <= -self.config['stop_loss']:
                    should_sell = True
                    reason = "硬止损"
                elif profit_pct >= position['target']:
                    drawdown = (position['highest_price'] - current_price) / position['highest_price']
                    if drawdown >= self.config['trailing_stop_ratio']:
                        should_sell = True
                        reason = f"移动止盈 ({position['target']:.2%})"
                
                if should_sell:
                    profit = (current_price - position['buy_price']) * position['shares']
                    total_profit += profit
                    capital += profit
                    capital_curve.append(capital)
                    
                    trades.append({
                        'date': i.date(),
                        'buy_time': position['buy_time'],
                        'sell_time': i,
                        'buy_price': position['buy_price'],
                        'sell_price': current_price,
                        'profit_pct': profit_pct,
                        'profit': profit,
                        'reason': reason,
                        'market_condition': position['market_condition'],
                        'score': position['score']
                    })
                    position = None
                    continue
            
            # 买入逻辑
            if position is None:
                if not allow_trade:
                    skipped_by_market += 1
                    continue
                
                # 时间过滤
                if '弱势' in market_reason:
                    no_buy_time = datetime.strptime('13:30', '%H:%M').time()
                elif row.get('is_weak_market', False):
                    no_buy_time = datetime.strptime(self.config['no_buy_time_weak'], '%H:%M').time()
                else:
                    no_buy_time = datetime.strptime(self.config['no_buy_time_normal'], '%H:%M').time()
                
                if current_time >= no_buy_time:
                    continue
                
                # 评分检查
                score = self.scorer.calculate_total(row)
                
                if score >= threshold:
                    shares = int(self.config['t_position_amount'] / current_price / 100) * 100
                    if shares > 0:
                        position = {
                            'buy_price': current_price,
                            'buy_time': i,
                            'shares': shares,
                            'highest_price': current_price,
                            'target': row.get('dynamic_profit_target', self.config['base_profit_target']),
                            'score': score,
                            'market_condition': market_reason.split()[0]
                        }
            
            capital_curve.append(capital)
        
        # 生成报告
        return self._generate_report(trades, capital, capital_curve, skipped_by_market)
    
    def _generate_report(self, trades, capital, capital_curve, skipped_by_market):
        """生成回测报告"""
        if not trades:
            print("❌ 无交易")
            return None
        
        df_trades = pd.DataFrame(trades)
        win_rate = (df_trades['profit_pct'] > 0).mean()
        total_return = (capital - self.config['t_position_amount']) / self.config['t_position_amount']
        
        wins = df_trades[df_trades['profit_pct'] > 0]
        losses = df_trades[df_trades['profit_pct'] <= 0]
        
        avg_win = wins['profit_pct'].mean() if len(wins) > 0 else 0
        avg_loss = abs(losses['profit_pct'].mean()) if len(losses) > 0 else 0
        pl_ratio = avg_win / avg_loss if avg_loss > 0 else 999
        
        print(f"📊 交易次数：{len(trades)}")
        print(f"🚫 被大盘过滤跳过：{skipped_by_market} 次")
        print(f"🎯 胜率：{win_rate:.2%}")
        print(f"💰 总收益率：{total_return:.2%}")
        print(f"💵 总盈利：{df_trades['profit'].sum():.2f} 元")
        print(f"📈 平均盈利：{avg_win:.2%}")
        print(f"📉 平均亏损：{avg_loss:.2%}")
        print(f"⚖️ 盈亏比：{pl_ratio:.2f}")
        print("-" * 60)
        
        # 市场环境细分
        normal = df_trades[df_trades['market_condition'] == '大盘正常']
        weak = df_trades[df_trades['market_condition'] == '大盘弱势']
        strong = df_trades[df_trades['market_condition'] == '大盘强势']
        
        if len(strong) > 0:
            print(f"   大盘强势：{len(strong)}次，胜率 {(strong['profit_pct']>0).mean():.2%}")
        if len(normal) > 0:
            print(f"   大盘正常：{len(normal)}次，胜率 {(normal['profit_pct']>0).mean():.2%}")
        if len(weak) > 0:
            print(f"   大盘弱势：{len(weak)}次，胜率 {(weak['profit_pct']>0).mean():.2%}")
        
        # 保存结果
        df_trades.to_csv('v56_backtest_trades.csv', encoding='utf_8_sig', index=False)
        print("\n✅ 交易明细已保存：v56_backtest_trades.csv")
        
        return df_trades


# ==================== 实盘监控 ====================
class RealtimeMonitor:
    """V5.6 实盘监控"""
    
    def __init__(self, config, fetcher, processor, scorer, market_filter):
        self.config = config
        self.fetcher = fetcher
        self.processor = processor
        self.scorer = scorer
        self.market_filter = market_filter
        
        self.position = None
        self.today_trades = 0
        self.consecutive_losses = 0
    
    def run(self):
        """运行实时监控"""
        print("\n" + "=" * 60)
        print("🔴 开始 V5.6 实盘监控")
        print("=" * 60)
        print(f"股票：{self.config['stock_code']} {self.config['stock_name']}")
        print(f"刷新间隔：{self.config['realtime_interval']} 秒")
        print("按 Ctrl+C 停止")
        print("=" * 60)
        
        try:
            while True:
                now = datetime.now()
                
                # 只在工作日交易时间监控
                if now.weekday() < 5 and time(9, 30) <= now.time() <= time(15, 0):
                    # 获取实时数据
                    quote = self.fetcher.get_realtime_quote()
                    
                    if quote:
                        # 整合数据
                        current_data = self._prepare_realtime_data(quote)
                        
                        if current_data is not None:
                            # 计算评分
                            score = self.scorer.calculate_total(current_data)
                            
                            # 大盘过滤
                            allow_trade, threshold, market_reason = self.market_filter.check(
                                self.fetcher.market_5min_df, 
                                now, 
                                current_data.get('is_weak_market', False))
                            
                            # 输出
                            self._print_status(now, quote, current_data, score, 
                                             allow_trade, threshold, market_reason)
                            
                            # 信号判断
                            if allow_trade and score >= threshold and self.position is None:
                                print(f"\n🟢 买入信号！评分={score:.2f} >= 阈值={threshold}")
                                # 这里可以接入实际交易接口
                            
                    time_module.sleep(self.config['realtime_interval'])
                else:
                    time_module.sleep(60)
                    
        except KeyboardInterrupt:
            print("\n\n⏹️ 监控已停止")
    
    def _prepare_realtime_data(self, quote):
        """准备实时数据（整合历史 + 实时）"""
        if self.fetcher.stock_5min_df is None:
            return None
        
        # 将实时数据追加到历史数据
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
        
        # 处理数据
        yesterday_vol = self.fetcher.get_yesterday_volume()
        processed = self.processor.process_stock_data(df, yesterday_vol)
        
        if processed is not None:
            return processed.iloc[-1]
        return None
    
    def _print_status(self, now, quote, data, score, allow_trade, threshold, market_reason):
        """打印状态"""
        print(f"\n[{now.strftime('%H:%M:%S')}] {self.config['stock_code']}")
        print(f"   当前价：{quote['current']:.2f} 元 ({quote['change_pct']*100:+.2f}%)")
        print(f"   VWAP 偏离：{(quote['current']/data['vwap']-1)*100:.2f}%")
        print(f"   日内位置：{data['intraday_pos']*100:.1f}%")
        print(f"   RSI6/14: {data['rsi_6']:.1f} / {data['rsi_14']:.1f}")
        print(f"   量比：{quote['volume_hand']/data['yesterday_volume']:.2f}")
        print(f"   综合评分：{score:.2f}")
        print(f"   {market_reason}")
        
        if allow_trade:
            if score >= threshold:
                print(f"   🟢 可买入 (评分={score:.2f} >= {threshold})")
            elif score >= threshold - 0.1:
                print(f"   🟡 观望 (接近信号)")
            else:
                print(f"   🔴 无信号")
        else:
            print(f"   🔴 大盘禁止交易")


# ==================== 主程序 ====================
def main():
    """主程序入口"""
    print("=" * 60)
    print("🏆 V5.6 终极完整版策略系统")
    print("=" * 60)
    print(f"股票：{CONFIG['stock_code']} {CONFIG['stock_name']}")
    print(f"模式：{CONFIG['mode']}")
    print("=" * 60)
    
    # 初始化组件
    fetcher = DataFetcher(CONFIG)
    processor = DataProcessor(CONFIG)
    scorer = V56Scorer(CONFIG)
    market_filter = MarketFilter(CONFIG)
    
    # 准备数据
    if CONFIG['mode'] == 'backtest':
        success = fetcher.prepare_data(
            mode='backtest',
            start_date=CONFIG['backtest_start_date'],
            end_date=CONFIG['backtest_end_date']
        )
        
        if success:
            # 处理数据
            yesterday_vol = fetcher.get_yesterday_volume()
            stock_df = processor.process_stock_data(fetcher.stock_5min_df, yesterday_vol)
            market_df = processor.process_market_data(fetcher.market_5min_df) if fetcher.market_5min_df is not None else None
            
            # 运行回测
            backtester = Backtester(CONFIG, scorer, market_filter)
            backtester.run(stock_df, market_df)
        else:
            print("❌ 数据准备失败")
    
    else:  # realtime
        success = fetcher.prepare_data(mode='realtime')
        
        if success:
            # 处理历史数据
            yesterday_vol = fetcher.get_yesterday_volume()
            processor.process_stock_data(fetcher.stock_5min_df, yesterday_vol)
            if fetcher.market_5min_df is not None:
                processor.process_market_data(fetcher.market_5min_df)
            
            # 运行实时监控
            monitor = RealtimeMonitor(CONFIG, fetcher, processor, scorer, market_filter)
            monitor.run()
        else:
            print("❌ 数据准备失败")


if __name__ == '__main__':
    main()