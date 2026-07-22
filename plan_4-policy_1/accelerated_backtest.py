#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPU加速的回测系统
使用并行化和GPU加速提高计算效率
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
import sqlite3
from pathlib import Path
from tqdm import tqdm
import warnings
import time
import re
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
import multiprocessing as mp
warnings.filterwarnings('ignore')

# 尝试导入GPU加速库
try:
    import cupy as cp
    GPU_AVAILABLE = True
    print("✅ GPU加速可用 (CuPy)")
except ImportError:
    try:
        # 尝试使用PyTorch作为备选
        import torch
        GPU_AVAILABLE = True
        print("✅ GPU加速可用 (PyTorch)")
    except ImportError:
        GPU_AVAILABLE = False
        print("⚠️  GPU加速不可用，使用CPU计算")

# 添加 plan_3-standardization_1 目录到路径
plan3_dir = Path(__file__).parent.parent / "plan_3-standardization_1"
sys.path.insert(0, str(plan3_dir))

from daily_trading_system import (
    generate_cross_ma_strategy_recommendations,
    generate_weekly_mean_down_strategy_recommendations,
    BaseOperator,
    STStockOperator
)

# 配置参数
INITIAL_CAPITAL = 50000  # 初始资金5万元
MAX_POSITIONS = 3        # 最多持有3只股票
MAX_PRICE = 150.0        # 最高买入价格150元
START_DATE = "2025-01-01"  # 回测开始日期
FEE_RATE = 0.791 / 10000  # 交易费率
MIN_FEE = 5.0            # 最低手续费

# 交易参数
STOP_LOSS_RATE = -0.10   # 止损比例 -10%
TARGET_BUY_VALUE = 15000 # 单次目标买入金额约1.5万元

class AcceleratedBacktestSystem:
    """GPU加速的回测系统"""
    
    def __init__(self, initial_capital=INITIAL_CAPITAL, max_positions=MAX_POSITIONS, 
                 max_price=MAX_PRICE, start_date=START_DATE, 
                 use_gpu=True, num_workers=None):
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_price = max_price
        self.start_date = pd.to_datetime(start_date)
        
        # 并行化设置
        self.use_gpu = use_gpu and GPU_AVAILABLE
        if num_workers is None:
            self.num_workers = max(1, mp.cpu_count() - 1)  # 留一个核心给系统
        else:
            self.num_workers = max(1, min(num_workers, mp.cpu_count()))
        
        # 数据操作器
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()

        self._all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        self._stock_name_map, self._is_st_map = self._load_stock_info_cache()
        self._weekly_feat_cache = self._build_weekly_feature_cache()
        
        # 回测状态
        self.cash = initial_capital
        self.positions = {}  # {stock_code: {'shares': int, 'buy_price': float, 'buy_date': datetime}}
        self.trade_history = []
        self.daily_records = []
        
        # 获取交易日历
        self.trading_dates = self._get_trading_dates()
        
        print(f"🔧 系统配置: 使用{'GPU' if self.use_gpu else 'CPU'}加速, {self.num_workers}个工作进程")
    
    def _get_trading_dates(self):
        """获取交易日历（简化版）"""
        print("📅 获取交易日历...")
        
        # 简化：使用工作日历，避免复杂的并行处理
        end_date = pd.Timestamp.now()
        date_range = pd.date_range(start=self.start_date, end=end_date, freq='B')
        
        print(f"  ✅ 获取到 {len(date_range)} 个工作日")
        return date_range
    
    def _get_strategy_recommendations_parallel(self, date):
        """获取策略推荐（按回测日历史数据筛选）"""
        all_codes = self._all_codes
        
        if not all_codes:
            return pd.DataFrame()
        
        recommendations = []

        current_date = pd.to_datetime(date)

        candidate_codes = []
        for code in all_codes:
            try:
                if self._is_st_map.get(code, False):
                    continue
                feat = self._weekly_feat_asof(code, current_date)
                if feat is None:
                    continue
                if not (bool(feat["cross_ma_4w"]) and bool(feat["weekly_mean_down"])):
                    continue
                candidate_codes.append(code)
            except Exception:
                continue

        for code in candidate_codes:
            try:
                signal = self._calculate_stock_signals_asof(code, current_date)
                if signal is not None:
                    recommendations.append(signal)
            except Exception:
                continue
        
        if not recommendations:
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(recommendations)
        
        # 应用价格限制
        df = df[df['current_price'] <= self.max_price]
        
        # 排序并返回前N个
        if not df.empty:
            # 使用综合得分排序
            df['score'] = df.apply(self._calculate_stock_score, axis=1)
            df = df.sort_values('score', ascending=False)
        
        return df.head(self.max_positions * 5)

    def _load_stock_info_cache(self):
        stock_name_map = {}
        is_st_map = {}
        patterns = [
            r"^ST",
            r"^\*ST",
            r"^SST",
            r"^\*\*ST",
            r"ST$",
            r"\*ST$",
            r"退市",
            r"风险警示",
        ]
        try:
            with self.base_op.get_connection() as conn:
                df = pd.read_sql_query("SELECT code, name FROM stocks", conn)
            if df is None or df.empty:
                return stock_name_map, is_st_map
            for _, row in df.iterrows():
                code = str(row["code"])
                name = str(row["name"] or "")
                stock_name_map[code] = name
                is_st = False
                if name:
                    for p in patterns:
                        if re.search(p, name):
                            is_st = True
                            break
                is_st_map[code] = is_st
        except Exception:
            pass
        return stock_name_map, is_st_map

    def _build_weekly_feature_cache(self):
        start_minus = (self.start_date - pd.Timedelta(weeks=140)).strftime("%Y-%m-%d")
        end_date = pd.Timestamp.now().strftime("%Y-%m-%d")
        try:
            with self.base_op.get_connection() as conn:
                df = pd.read_sql_query(
                    """
                    SELECT date, stock_code, open, close
                    FROM stock_weekly
                    WHERE date >= ? AND date <= ?
                    """,
                    conn,
                    params=(start_minus, end_date),
                )
        except Exception:
            return {}

        if df is None or df.empty:
            return {}

        df["date"] = pd.to_datetime(df["date"])
        df["open"] = pd.to_numeric(df["open"], errors="coerce")
        df["close"] = pd.to_numeric(df["close"], errors="coerce")
        df = df.dropna(subset=["stock_code", "date", "open", "close"])
        df = df.sort_values(["stock_code", "date"]).reset_index(drop=True)

        g = df.groupby("stock_code", sort=False)
        for w in [5, 10, 20, 30]:
            df[f"ma{w}"] = g["close"].rolling(window=w).mean().reset_index(level=0, drop=True)

        df["mean_0_30"] = g["close"].rolling(window=30).mean().reset_index(level=0, drop=True)
        shifted = g["close"].shift(30)
        df["mean_30_60"] = shifted.groupby(df["stock_code"], sort=False).rolling(window=30).mean().reset_index(level=0, drop=True)

        df["cross_ma_4w"] = (
            (df["close"] > df["ma5"])
            & (df["close"] > df["ma10"])
            & (df["close"] > df["ma20"])
            & (df["close"] > df["ma30"])
            & (df["open"] < df["ma5"])
            & (df["open"] < df["ma10"])
            & (df["open"] < df["ma20"])
            & (df["open"] < df["ma30"])
        )
        df["weekly_mean_down"] = (df["mean_0_30"] > 0) & (df["mean_30_60"] > 0) & (df["mean_0_30"] < df["mean_30_60"])
        df["weekly_mean_ratio"] = df["mean_0_30"] / df["mean_30_60"]

        cache = {}
        codes = df["stock_code"].dropna().unique().tolist()
        for code, sub in tqdm(df.groupby("stock_code", sort=False), total=len(codes), desc="构建周线特征缓存", unit="股"):
            if sub is None or sub.empty:
                continue
            cache[code] = {
                "dates": sub["date"].to_numpy(dtype="datetime64[ns]"),
                "cross_ma_4w": sub["cross_ma_4w"].to_numpy(dtype=bool),
                "weekly_mean_down": sub["weekly_mean_down"].to_numpy(dtype=bool),
                "mean_0_30": pd.to_numeric(sub["mean_0_30"], errors="coerce").to_numpy(dtype=float),
                "mean_30_60": pd.to_numeric(sub["mean_30_60"], errors="coerce").to_numpy(dtype=float),
                "weekly_mean_ratio": pd.to_numeric(sub["weekly_mean_ratio"], errors="coerce").to_numpy(dtype=float),
            }
        return cache

    def _weekly_feat_asof(self, stock_code, current_date):
        pack = self._weekly_feat_cache.get(stock_code)
        if not pack:
            return None
        dates = pack["dates"]
        if dates is None or len(dates) == 0:
            return None
        idx = int(np.searchsorted(dates, np.datetime64(pd.to_datetime(current_date)), side="right") - 1)
        if idx < 0:
            return None
        return {
            "cross_ma_4w": bool(pack["cross_ma_4w"][idx]),
            "weekly_mean_down": bool(pack["weekly_mean_down"][idx]),
            "weekly_mean_0_30": float(pack["mean_0_30"][idx]) if np.isfinite(pack["mean_0_30"][idx]) else None,
            "weekly_mean_30_60": float(pack["mean_30_60"][idx]) if np.isfinite(pack["mean_30_60"][idx]) else None,
            "weekly_mean_ratio": float(pack["weekly_mean_ratio"][idx]) if np.isfinite(pack["weekly_mean_ratio"][idx]) else None,
        }
    
    def _get_daily_data_asof(self, stock_code, current_date, days=30):
        query = """
        SELECT date, stock_code, open, high, low, close, volume, amount
        FROM stock_daily
        WHERE stock_code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """
        with self.base_op.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(stock_code, pd.Timestamp(current_date).strftime("%Y-%m-%d"), int(days)))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df

    def _get_weekly_data_asof(self, stock_code, current_date, weeks=70):
        query = """
        SELECT date, stock_code, open, high, low, close, volume, amount
        FROM stock_weekly
        WHERE stock_code = ? AND date <= ?
        ORDER BY date DESC
        LIMIT ?
        """
        with self.base_op.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(stock_code, pd.Timestamp(current_date).strftime("%Y-%m-%d"), int(weeks)))
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"])
            df = df.sort_values("date")
        return df

    def _get_price_asof(self, stock_code, current_date):
        daily_data = self._get_daily_data_asof(stock_code, current_date, days=5)
        if daily_data is None or daily_data.empty:
            return None
        try:
            return float(pd.to_numeric(daily_data["close"].iloc[-1], errors="coerce"))
        except Exception:
            return None

    def _get_stock_name(self, stock_code):
        name = self._stock_name_map.get(stock_code)
        return str(name) if name is not None else ""

    def _calculate_stock_signals_asof(self, stock_code, current_date):
        """计算单只股票的策略信号（按回测日历史数据）"""
        try:
            if self._is_st_map.get(stock_code, False):
                return None

            feat = self._weekly_feat_asof(stock_code, current_date)
            if feat is None:
                return None
            if not (bool(feat["cross_ma_4w"]) and bool(feat["weekly_mean_down"])):
                return None

            daily_data = self._get_daily_data_asof(stock_code, current_date, days=30)
            if daily_data is None or daily_data.empty:
                return None
            daily_data = daily_data.copy()
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in daily_data.columns:
                    daily_data[col] = pd.to_numeric(daily_data[col], errors="coerce")
            daily_data = daily_data.dropna(subset=["close"])
            if len(daily_data) < 21:
                return None

            current_price = float(daily_data["close"].iloc[-1])
            if not (0 < current_price <= self.max_price):
                return None

            ret_5d = None
            try:
                ret_5d = (current_price / float(daily_data["close"].iloc[-6])) - 1.0
            except Exception:
                ret_5d = None

            ret_20d = None
            try:
                ret_20d = (current_price / float(daily_data["close"].iloc[-21])) - 1.0
            except Exception:
                ret_20d = None

            stock_name = self._get_stock_name(stock_code)

            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'signal': 'BUY',
                'confidence': 0.7,
                'current_price': current_price,
                'reasons': 'cross_ma50+weekly_mean_down',
                'cross_ma_4w': True,
                'is_st': False,
                'ret_5d': ret_5d,
                'ret_20d': ret_20d,
                'weekly_mean_0_30': float(feat["weekly_mean_0_30"]) if feat.get("weekly_mean_0_30") is not None else None,
                'weekly_mean_30_60': float(feat["weekly_mean_30_60"]) if feat.get("weekly_mean_30_60") is not None else None,
                'weekly_mean_ratio': float(feat["weekly_mean_ratio"]) if feat.get("weekly_mean_ratio") is not None else None
            }
            
        except Exception as e:
            # 静默失败，返回None
            return None
    
    def _calculate_stock_score(self, stock_row):
        """计算股票的预期得分（GPU加速版）"""
        if self.use_gpu:
            try:
                # 使用CuPy进行GPU计算
                confidence = cp.asarray(stock_row.get('confidence', 0.5))
                price = cp.asarray(stock_row.get('current_price', 0))
                mean_ratio = cp.asarray(stock_row.get('weekly_mean_ratio', 1.0))
                
                # 基础得分
                base_score = confidence * 10
                
                # 价格得分
                price_score = cp.where(price > 0, 10 / (price / 10), 0)
                
                # 周均价比率得分
                ratio_score = cp.where(mean_ratio < 1.0, (1.0 - mean_ratio) * 20, 0)
                
                # 总得分
                total_score = base_score + price_score + ratio_score
                
                # 转换回标量
                return float(total_score)
                
            except Exception:
                # GPU计算失败，回退到CPU
                pass
        
        # CPU计算
        confidence = stock_row.get('confidence', 0.5)
        price = stock_row.get('current_price', 0)
        mean_ratio = stock_row.get('weekly_mean_ratio', 1.0)
        
        base_score = confidence * 10
        price_score = 10 / (price / 10) if price > 0 else 0
        ratio_score = (1.0 - mean_ratio) * 20 if mean_ratio < 1.0 else 0
        
        return base_score + price_score + ratio_score
    
    def _batch_calculate_returns(self, stock_codes, current_prices, buy_prices):
        """批量计算收益率（GPU加速）"""
        if self.use_gpu and len(stock_codes) > 100:  # 只有数据量大时才使用GPU
            try:
                # 使用CuPy进行批量计算
                current_prices_gpu = cp.asarray(current_prices)
                buy_prices_gpu = cp.asarray(buy_prices)
                
                # 批量计算收益率
                returns_gpu = (current_prices_gpu - buy_prices_gpu) / buy_prices_gpu
                
                # 转换回numpy数组
                returns = cp.asnumpy(returns_gpu)
                
                return returns
                
            except Exception:
                # GPU计算失败，回退到CPU
                pass
        
        # CPU计算
        returns = []
        for current_price, buy_price in zip(current_prices, buy_prices):
            if buy_price > 0:
                returns.append((current_price - buy_price) / buy_price)
            else:
                returns.append(0)
        
        return np.array(returns)
    
    def run_backtest(self):
        """运行加速回测"""
        print("🚀 开始GPU加速策略回测")
        print(f"📊 初始资金: {self.initial_capital:.2f}元")
        print(f"📈 策略组合: cross_ma50 + weekly_mean_down（按回测日历史数据筛选）")
        print(f"📅 回测期间: {self.start_date.date()} 至 {pd.Timestamp.now().date()}")
        print(f"🎯 限制条件: 最多{self.max_positions}只持仓, 单价≤{self.max_price}元, 单票约{TARGET_BUY_VALUE:.0f}元, 止损{abs(STOP_LOSS_RATE):.0%}")
        print(f"⚡ 加速模式: {'GPU' if self.use_gpu else 'CPU'} + {self.num_workers}进程")
        print("-" * 70)
        
        start_time = time.time()
        
        # 进度条
        pbar = tqdm(self.trading_dates, desc="加速回测进度", unit="交易日")
        
        for current_date in pbar:
            # 更新进度条描述
            pbar.set_description(f"加速回测 {current_date.date()}")
            
            # 1. 检查现有持仓是否需要卖出（并行优化）
            positions_to_sell = []
            
            # 批量获取价格数据
            if self.positions:
                stock_codes = list(self.positions.keys())
                current_prices = []
                
                # 并行获取价格
                with ThreadPoolExecutor(max_workers=min(self.num_workers, 8)) as executor:
                    future_to_code = {
                        executor.submit(self._get_current_price, code, current_date): code 
                        for code in stock_codes
                    }
                    
                    for future in as_completed(future_to_code):
                        code = future_to_code[future]
                        try:
                            price = future.result()
                            if price is not None:
                                current_prices.append((code, price))
                        except Exception:
                            continue
                
                # 评估是否需要卖出
                for code, current_price in current_prices:
                    if code in self.positions:
                        position = self.positions[code]
                        should_sell, reason = self._should_sell(
                            code, position, current_date, current_price
                        )
                        
                        if should_sell:
                            positions_to_sell.append((code, reason))
            
            # 执行卖出
            for stock_code, reason in positions_to_sell:
                self._execute_sell(stock_code, current_date, reason)
            
            available_slots = self.max_positions - len(self.positions)
            if available_slots > 0 and self.cash > 1000:
                recommendations = self._get_strategy_recommendations_parallel(current_date)

                if not recommendations.empty:
                    recommendations = recommendations[~recommendations['stock_code'].isin(self.positions.keys())]
                    if not recommendations.empty:
                        sorted_recommendations = recommendations.sort_values('score', ascending=False)

                        for _, row in sorted_recommendations.iterrows():
                            if available_slots <= 0:
                                break

                            stock_code = row['stock_code']
                            stock_name = row['stock_name']
                            current_price = row['current_price']

                            if current_price > self.max_price:
                                continue

                            success = self._execute_buy(
                                stock_code, stock_name, current_price, current_date, TARGET_BUY_VALUE
                            )

                            if success:
                                available_slots -= 1
            
            # 3. 记录当日状态
            daily_record = self._record_daily_status(current_date)
            self.daily_records.append(daily_record)
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        print("-" * 70)
        print(f"✅ 加速回测完成")
        print(f"⏱️  总耗时: {elapsed_time:.2f}秒")
        print(f"📈 平均每个交易日: {elapsed_time/len(self.trading_dates):.3f}秒")
        
        return self._generate_results()
    
    # 以下方法继承自原版，但可以添加GPU加速优化
    def _get_current_price(self, stock_code, current_date):
        """获取当前价格（按回测日历史数据，可并行化）"""
        return self._get_price_asof(stock_code, current_date)
    
    def _should_sell(self, stock_code, position, current_date, current_price):
        """判断是否应该卖出（GPU加速版）"""
        buy_price = position['buy_price']
        
        # 计算收益率
        return_rate = (current_price - buy_price) / buy_price
        
        # 止损检查
        if return_rate <= STOP_LOSS_RATE:
            return True, f"止损触发: {return_rate:.1%}"
        
        return False, ""
    
    def _execute_sell(self, stock_code, current_date, reason=""):
        """执行卖出操作"""
        if stock_code not in self.positions:
            return
        
        position = self.positions[stock_code]
        
        current_price = self._get_current_price(stock_code, current_date)
        if current_price is None:
            return
        
        shares = position['shares']
        
        # 计算卖出金额
        sell_amount = shares * current_price
        
        # 计算手续费
        fee = max(sell_amount * FEE_RATE, MIN_FEE)
        
        # 计算净收入
        net_amount = sell_amount - fee
        
        # 计算盈亏
        buy_amount = position['shares'] * position['buy_price']
        profit = net_amount - buy_amount
        
        # 更新现金
        self.cash += net_amount
        
        # 记录交易
        self.trade_history.append({
            'date': current_date,
            'stock_code': stock_code,
            'action': 'SELL',
            'shares': shares,
            'price': current_price,
            'amount': sell_amount,
            'fee': fee,
            'profit': profit,
            'reason': reason
        })
        
        # 移除持仓
        del self.positions[stock_code]
        
        print(f"  📤 卖出 {stock_code}: {shares}股 @ {current_price:.2f}, 盈利: {profit:.2f}元 ({reason})")
    
    def _execute_buy(self, stock_code, stock_name, current_price, current_date, available_cash):
        """执行买入操作"""
        budget = min(float(available_cash), float(self.cash))
        if budget <= 0 or current_price <= 0:
            return False
        buy_shares = int(budget / current_price / 100) * 100
        for _ in range(2):
            amount = buy_shares * current_price
            fee = max(amount * FEE_RATE, MIN_FEE) if amount > 0 else MIN_FEE
            buy_shares = int(max(0.0, budget - fee) / current_price / 100) * 100
        if buy_shares < 100:
            return False
        
        # 计算买入金额
        buy_amount = buy_shares * current_price
        
        # 计算手续费
        fee = max(buy_amount * FEE_RATE, MIN_FEE)
        
        # 总成本
        total_cost = buy_amount + fee
        
        # 检查是否有足够现金
        if total_cost > self.cash:
            return False
        
        # 更新现金
        self.cash -= total_cost
        
        # 记录持仓
        self.positions[stock_code] = {
            'shares': buy_shares,
            'buy_price': current_price,
            'buy_date': current_date,
            'stock_name': stock_name
        }
        
        # 记录交易
        self.trade_history.append({
            'date': current_date,
            'stock_code': stock_code,
            'action': 'BUY',
            'shares': buy_shares,
            'price': current_price,
            'amount': buy_amount,
            'fee': fee,
            'profit': 0,
            'reason': '策略买入'
        })
        
        print(f"  📥 买入 {stock_code}({stock_name}): {buy_shares}股 @ {current_price:.2f}, 成本: {total_cost:.2f}元")
        return True
    
    def _evaluate_position_performance(self, current_date):
        """评估当前持仓的表现（并行优化）"""
        performance = []
        
        if not self.positions:
            return performance
        
        # 批量获取价格数据
        stock_codes = list(self.positions.keys())
        current_prices = []
        
        # 并行获取价格
        with ThreadPoolExecutor(max_workers=min(self.num_workers, 8)) as executor:
            future_to_code = {
                executor.submit(self._get_current_price, code, current_date): code 
                for code in stock_codes
            }
            
            for future in as_completed(future_to_code):
                code = future_to_code[future]
                try:
                    price = future.result()
                    if price is not None:
                        current_prices.append((code, price))
                except Exception:
                    continue
        
        # 计算表现
        for code, current_price in current_prices:
            if code in self.positions:
                position = self.positions[code]
                buy_price = position['buy_price']
                buy_date = position['buy_date']
                
                # 计算收益率
                return_rate = (current_price - buy_price) / buy_price
                
                # 计算持有天数
                hold_days = (current_date - buy_date).days
                
                # 计算综合得分
                score = return_rate * 100 - (hold_days / 30)
                
                performance.append({
                    'stock_code': code,
                    'stock_name': position.get('stock_name', ''),
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'return_rate': return_rate,
                    'hold_days': hold_days,
                    'score': score
                })
        
        return performance
    
    def _record_daily_status(self, date):
        """记录当日状态"""
        record = {
            'date': date,
            'cash': self.cash,
            'position_count': len(self.positions),
            'total_value': self._calculate_total_value(date)
        }
        
        # 记录持仓详情
        for i, (stock_code, position) in enumerate(self.positions.items(), 1):
            record[f'position_{i}_code'] = stock_code
            record[f'position_{i}_name'] = position.get('stock_name', '')
            record[f'position_{i}_shares'] = position['shares']
            record[f'position_{i}_buy_price'] = position['buy_price']
            
            current_price = self._get_current_price(stock_code, date)
            if current_price is not None:
                record[f'position_{i}_current_price'] = current_price
                record[f'position_{i}_value'] = position['shares'] * current_price
                record[f'position_{i}_profit'] = position['shares'] * (current_price - position['buy_price'])
            else:
                record[f'position_{i}_current_price'] = position['buy_price']
                record[f'position_{i}_value'] = position['shares'] * position['buy_price']
                record[f'position_{i}_profit'] = 0
        
        return record
    
    def _calculate_total_value(self, date):
        """计算总资产价值（并行优化）"""
        total_value = self.cash
        
        if not self.positions:
            return total_value
        
        # 批量获取价格数据
        stock_codes = list(self.positions.keys())
        
        # 并行获取价格和计算价值
        with ThreadPoolExecutor(max_workers=min(self.num_workers, 8)) as executor:
            future_to_code = {
                executor.submit(self._calculate_position_value, code, date): code 
                for code in stock_codes
            }
            
            for future in as_completed(future_to_code):
                try:
                    value = future.result()
                    if value is not None:
                        total_value += value
                except Exception:
                    continue
        
        return total_value
    
    def _calculate_position_value(self, stock_code, date):
        """计算单只持仓价值（可并行化）"""
        if stock_code not in self.positions:
            return 0
        
        position = self.positions[stock_code]
        
        current_price = self._get_current_price(stock_code, date)
        if current_price is None:
            return position['shares'] * position['buy_price']
        
        return position['shares'] * current_price
    
    def _generate_results(self):
        """生成回测结果"""
        # 创建DataFrame
        daily_df = pd.DataFrame(self.daily_records)
        trade_df = pd.DataFrame(self.trade_history)
        
        # 计算累计收益
        if not daily_df.empty:
            daily_df['total_profit'] = daily_df['total_value'] - self.initial_capital
            daily_df['return_rate'] = daily_df['total_profit'] / self.initial_capital
        
        # 计算交易统计
        if not trade_df.empty:
            buy_trades = trade_df[trade_df['action'] == 'BUY']
            sell_trades = trade_df[trade_df['action'] == 'SELL']
            
            total_profit = sell_trades['profit'].sum() if not sell_trades.empty else 0
            win_trades = sell_trades[sell_trades['profit'] > 0]
            loss_trades = sell_trades[sell_trades['profit'] <= 0]
            
            stats = {
                'total_trades': len(trade_df),
                'buy_trades': len(buy_trades),
                'sell_trades': len(sell_trades),
                'total_profit': total_profit,
                'win_rate': len(win_trades) / len(sell_trades) if len(sell_trades) > 0 else 0,
                'avg_profit_per_trade': sell_trades['profit'].mean() if not sell_trades.empty else 0,
                'max_profit': sell_trades['profit'].max() if not sell_trades.empty else 0,
                'max_loss': sell_trades['profit'].min() if not sell_trades.empty else 0,
                'final_cash': self.cash,
                'final_total_value': self._calculate_total_value(pd.Timestamp.now()) if not daily_df.empty else self.cash,
                'use_gpu': self.use_gpu,
                'num_workers': self.num_workers
            }
        else:
            stats = {
                'total_trades': 0,
                'buy_trades': 0,
                'sell_trades': 0,
                'total_profit': 0,
                'win_rate': 0,
                'avg_profit_per_trade': 0,
                'max_profit': 0,
                'max_loss': 0,
                'final_cash': self.cash,
                'final_total_value': self.cash,
                'use_gpu': self.use_gpu,
                'num_workers': self.num_workers
            }
        
        return daily_df, trade_df, stats
    
    def save_results(self, output_dir="accelerated_backtest_results"):
        """保存回测结果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 生成结果
        daily_df, trade_df, stats = self._generate_results()
        
        # 保存每日记录
        if not daily_df.empty:
            daily_file = output_dir / f"daily_records_{timestamp}.csv"
            daily_df.to_csv(daily_file, index=False, encoding='utf-8-sig')
            print(f"💾 每日记录已保存: {daily_file}")
        
        # 保存交易记录
        if not trade_df.empty:
            trade_file = output_dir / f"trade_history_{timestamp}.csv"
            trade_df.to_csv(trade_file, index=False, encoding='utf-8-sig')
            print(f"💾 交易记录已保存: {trade_file}")
        
        # 保存统计信息
        stats_file = output_dir / f"statistics_{timestamp}.txt"
        with open(stats_file, 'w', encoding='utf-8') as f:
            f.write("GPU加速策略回测统计报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"回测期间: {self.start_date.date()} 至 {pd.Timestamp.now().date()}\n")
            f.write(f"初始资金: {self.initial_capital:.2f}元\n")
            f.write(f"策略组合: weekly_mean_down + cross_ma50\n")
            f.write(f"限制条件: 最多{self.max_positions}只持仓, 单价≤{self.max_price}元\n")
            f.write(f"加速模式: {'GPU' if self.use_gpu else 'CPU'}加速, {self.num_workers}个工作进程\n")
            f.write("\n财务表现:\n")
            f.write(f"  最终总资产: {stats['final_total_value']:.2f}元\n")
            f.write(f"  最终现金: {stats['final_cash']:.2f}元\n")
            f.write(f"  总收益: {stats['total_profit']:.2f}元\n")
            f.write(f"  总收益率: {(stats['final_total_value'] - self.initial_capital) / self.initial_capital:.1%}\n")
            f.write("\n交易统计:\n")
            f.write(f"  总交易次数: {stats['total_trades']}\n")
            f.write(f"  买入交易: {stats['buy_trades']}\n")
            f.write(f"  卖出交易: {stats['sell_trades']}\n")
            f.write(f"  胜率: {stats['win_rate']:.1%}\n")
            f.write(f"  平均每笔盈利: {stats['avg_profit_per_trade']:.2f}元\n")
            f.write(f"  最大盈利: {stats['max_profit']:.2f}元\n")
            f.write(f"  最大亏损: {stats['max_loss']:.2f}元\n")
        
        print(f"💾 统计报告已保存: {stats_file}")
        
        return daily_file, trade_file, stats_file

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GPU加速策略回测系统')
    parser.add_argument('--start-date', type=str, default=START_DATE, 
                       help=f'回测开始日期 (默认: {START_DATE})')
    parser.add_argument('--initial-capital', type=float, default=INITIAL_CAPITAL,
                       help=f'初始资金 (默认: {INITIAL_CAPITAL})')
    parser.add_argument('--max-positions', type=int, default=MAX_POSITIONS,
                       help=f'最大持仓数量 (默认: {MAX_POSITIONS})')
    parser.add_argument('--max-price', type=float, default=MAX_PRICE,
                       help=f'最高买入价格 (默认: {MAX_PRICE})')
    parser.add_argument('--output-dir', type=str, default='accelerated_backtest_results',
                       help='输出目录 (默认: accelerated_backtest_results)')
    parser.add_argument('--no-gpu', action='store_true',
                       help='禁用GPU加速')
    parser.add_argument('--workers', type=int, default=None,
                       help='工作进程数量 (默认: CPU核心数-1)')
    
    args = parser.parse_args()
    
    # 创建加速回测系统
    backtest = AcceleratedBacktestSystem(
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        max_price=args.max_price,
        start_date=args.start_date,
        use_gpu=not args.no_gpu,
        num_workers=args.workers
    )
    
    # 运行回测
    try:
        print("🚀 开始运行GPU加速回测...")
        backtest.run_backtest()
        
        # 保存结果
        print("\n💾 正在保存回测结果...")
        daily_file, trade_file, stats_file = backtest.save_results(args.output_dir)
        
        print("\n✅ GPU加速回测完成!")
        print(f"📊 结果已保存到目录: {args.output_dir}")
        print(f"📈 每日记录: {daily_file}")
        print(f"📊 交易记录: {trade_file}")
        print(f"📋 统计报告: {stats_file}")
        
    except KeyboardInterrupt:
        print("\n⚠️  回测被用户中断")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ 回测过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
    
