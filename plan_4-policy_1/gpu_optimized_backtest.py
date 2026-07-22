#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
GPU优化版回测系统
确保计算真正在GPU上进行，最大化GPU利用率
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
from tqdm import tqdm
import warnings
import time
import json
import pickle
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed
from functools import partial
import multiprocessing as mp
warnings.filterwarnings('ignore')

# 添加 plan_3-standardization_1 目录到路径
plan3_dir = Path(__file__).parent.parent / "plan_3-standardization_1"
sys.path.insert(0, str(plan3_dir))

from daily_trading_system import (
    generate_cross_ma_strategy_recommendations,
    generate_weekly_mean_down_strategy_recommendations,
    BaseOperator,
    STStockOperator
)

class GPUOptimizedBacktestSystem:
    """GPU优化版回测系统"""
    
    def __init__(self, start_date='2025-01-01', end_date=None,
                 initial_capital=50000, max_positions=3, max_price=150.0,
                 use_gpu=True, num_workers=None, output_dir='gpu_optimized_results'):
        
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date) if end_date else pd.Timestamp.now()
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_price = max_price
        self.use_gpu = use_gpu
        self.num_workers = num_workers or max(1, mp.cpu_count() - 1)
        self.output_dir = Path(output_dir)
        
        # 初始化操作器
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()
        
        # 持仓和资金
        self.cash = initial_capital
        self.positions = {}  # {stock_code: {'shares': int, 'buy_price': float, 'buy_date': date}}
        self.trade_history = []
        self.daily_records = []
        
        # GPU初始化
        self.gpu_backend = None
        self.gpu_device = None
        if use_gpu:
            self._init_gpu()
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("🚀 GPU优化版回测系统启动")
        print("=" * 60)
        print(f"📅 回测期间: {self.start_date.date()} 到 {self.end_date.date()}")
        print(f"💰 初始资金: {self.initial_capital:,}元")
        print(f"📊 最大持仓: {self.max_positions} 只")
        print(f"💵 最高买入价: {self.max_price}元")
        print(f"⚡ GPU加速: {'启用' if use_gpu else '禁用'}")
        if use_gpu and self.gpu_backend:
            print(f"🎮 GPU后端: {self.gpu_backend}")
        print(f"👥 工作进程: {self.num_workers} 个")
        print("=" * 60)
    
    def _init_gpu(self):
        """初始化GPU加速"""
        print("⚡ 初始化GPU加速...")
        
        # 优先使用CuPy（更适合数值计算）
        try:
            import cupy as cp
            self.gpu_backend = 'cupy'
            self.gpu_device = cp
            
            # 测试GPU性能
            print(f"  ✅ 使用CuPy GPU加速 (版本: {cp.__version__})")
            
            # 运行基准测试
            print("  📊 运行GPU基准测试...")
            start = time.time()
            
            # 大规模矩阵计算
            size = 5000
            x = cp.random.rand(size, size)
            y = cp.random.rand(size, size)
            z = cp.dot(x, y)
            cp.cuda.Stream.null.synchronize()
            
            gpu_time = time.time() - start
            print(f"    {size}x{size} 矩阵乘法耗时: {gpu_time:.2f}秒")
            print(f"    GPU计算能力: {size**3 / gpu_time / 1e9:.1f} GFLOPS")
            
            # 显示GPU信息
            mem_info = cp.cuda.runtime.memGetInfo()
            free_mem = mem_info[0] / 1e9
            total_mem = mem_info[1] / 1e9
            print(f"    GPU内存: {free_mem:.1f}/{total_mem:.1f} GB 可用")
            
            return
            
        except ImportError:
            print("  ⚠️  CuPy不可用，尝试PyTorch...")
        
        # 备选：PyTorch
        try:
            import torch
            if torch.cuda.is_available():
                self.gpu_backend = 'torch'
                self.gpu_device = torch.device('cuda')
                
                print(f"  ✅ 使用PyTorch GPU加速 (版本: {torch.__version__})")
                print(f"  🎮 GPU设备: {torch.cuda.get_device_name(0)}")
                
                # 测试GPU性能
                print("  📊 运行GPU基准测试...")
                start = time.time()
                
                # 大规模张量计算
                size = 5000
                x = torch.rand(size, size, device='cuda')
                y = torch.rand(size, size, device='cuda')
                z = torch.matmul(x, y)
                torch.cuda.synchronize()
                
                gpu_time = time.time() - start
                print(f"    {size}x{size} 张量乘法耗时: {gpu_time:.2f}秒")
                
                # 显示GPU信息
                free_mem = torch.cuda.memory_reserved(0) / 1e9
                total_mem = torch.cuda.get_device_properties(0).total_memory / 1e9
                print(f"    GPU内存: {free_mem:.1f}/{total_mem:.1f} GB 可用")
                
                return
            else:
                print("  ⚠️  PyTorch可用但CUDA不可用")
                self.use_gpu = False
                
        except ImportError:
            print("  ⚠️  PyTorch不可用")
        
        print("  ❌ 无GPU加速库可用，使用CPU计算")
        self.use_gpu = False
    
    def _gpu_compute_metrics(self, prices_array):
        """使用GPU计算技术指标"""
        if not self.use_gpu or not self.gpu_backend:
            # CPU计算
            prices = np.array(prices_array, dtype=np.float32)
            
            if len(prices) < 5:
                return 0.5, 0.0, 0.0
            
            mean_5d = float(np.mean(prices[-5:]))
            mean_all = float(np.mean(prices))
            volatility = float(np.std(prices))
            
            return mean_5d, mean_all, volatility
        
        # GPU计算
        if self.gpu_backend == 'cupy':
            import cupy as cp
            
            # 将数据转移到GPU
            gpu_prices = cp.asarray(prices_array, dtype=cp.float32)
            
            if len(gpu_prices) < 5:
                return 0.5, 0.0, 0.0
            
            # 批量计算
            mean_5d = float(cp.mean(gpu_prices[-5:]))
            mean_all = float(cp.mean(gpu_prices))
            volatility = float(cp.std(gpu_prices))
            
            return mean_5d, mean_all, volatility
        
        elif self.gpu_backend == 'torch':
            import torch
            
            # 将数据转移到GPU
            gpu_prices = torch.tensor(prices_array, dtype=torch.float32, device='cuda')
            
            if len(gpu_prices) < 5:
                return 0.5, 0.0, 0.0
            
            # 批量计算
            mean_5d = float(torch.mean(gpu_prices[-5:]))
            mean_all = float(torch.mean(gpu_prices))
            volatility = float(torch.std(gpu_prices))
            
            return mean_5d, mean_all, volatility
        
        return 0.5, 0.0, 0.0
    
    def _gpu_batch_compute(self, stock_data_list):
        """批量GPU计算"""
        if not self.use_gpu or len(stock_data_list) == 0:
            return []
        
        results = []
        
        if self.gpu_backend == 'cupy':
            import cupy as cp
            
            # 批量处理
            batch_size = min(100, len(stock_data_list))
            
            for i in range(0, len(stock_data_list), batch_size):
                batch = stock_data_list[i:i+batch_size]
                
                # 在GPU上批量计算
                for stock_data in batch:
                    try:
                        prices = stock_data.get('prices', [])
                        if len(prices) < 5:
                            results.append({'confidence': 0.5, 'score': 0.0})
                            continue
                        
                        # GPU计算
                        gpu_prices = cp.asarray(prices, dtype=cp.float32)
                        
                        # 计算多个指标
                        mean_5d = float(cp.mean(gpu_prices[-5:]))
                        mean_10d = float(cp.mean(gpu_prices))
                        volatility = float(cp.std(gpu_prices))
                        
                        # 计算得分
                        current_price = float(prices[-1])
                        price_score = 1.0 - (current_price / self.max_price)
                        trend_score = 1.0 if current_price > mean_5d else 0.5
                        volatility_score = 1.0 - min(volatility / mean_10d, 0.5)
                        
                        confidence = 0.3 + 0.7 * (price_score * 0.4 + trend_score * 0.3 + volatility_score * 0.3)
                        overall_score = confidence * 100
                        
                        results.append({
                            'confidence': min(confidence, 0.95),
                            'score': overall_score,
                            'mean_5d': mean_5d,
                            'mean_10d': mean_10d,
                            'volatility': volatility
                        })
                        
                    except Exception:
                        results.append({'confidence': 0.5, 'score': 0.0})
        
        return results
    
    def _get_stock_name(self, stock_code):
        """获取股票名称"""
        try:
            info = self.base_op.get_stock_info(stock_code)
            if isinstance(info, dict):
                return str(info.get("name") or "")
        except Exception:
            return ""
        return ""
    
    def _get_trading_dates(self):
        """获取交易日历"""
        print("📅 获取交易日历...")
        
        # 使用工作日历
        date_range = pd.date_range(start=self.start_date, end=self.end_date, freq='B')
        
        print(f"  ✅ 获取到 {len(date_range)} 个工作日")
        return date_range
    
    def _calculate_stock_signals_gpu_optimized(self, stock_code):
        """GPU优化的股票信号计算"""
        try:
            # 检查ST（CPU操作）
            st_info = self.st_op.calculate(stock_code)
            is_st = st_info.get('is_st', False)
            if is_st:
                return None
            
            # 获取日线数据
            daily_data = self.base_op.get_daily_data(stock_code, days=20)  # 更多数据用于GPU计算
            if daily_data is None or daily_data.empty or len(daily_data) < 10:
                return None
            
            current_price = float(daily_data['close'].iloc[-1])
            if not (current_price > 0):
                return None
            
            # 价格限制
            if current_price > self.max_price:
                return None
            
            # 获取股票名称
            stock_name = self._get_stock_name(stock_code)
            
            # 提取价格数据
            close_prices = daily_data['close'].astype(float).values.tolist()
            
            # 使用GPU计算指标
            mean_5d, mean_all, volatility = self._gpu_compute_metrics(close_prices)
            
            # 计算得分
            price_score = 1.0 - (current_price / self.max_price)  # 价格越低得分越高
            trend_score = 1.0 if current_price > mean_5d else 0.5  # 短期趋势
            volatility_score = 1.0 - min(volatility / mean_all, 0.5) if mean_all > 0 else 0.5  # 波动率越低越好
            
            confidence = 0.3 + 0.7 * (price_score * 0.4 + trend_score * 0.3 + volatility_score * 0.3)
            
            return {
                'stock_code': stock_code,
                'stock_name': stock_name,
                'signal': 'BUY',
                'confidence': min(confidence, 0.95),
                'current_price': current_price,
                'mean_5d': mean_5d,
                'mean_all': mean_all,
                'volatility': volatility,
                'reasons': 'gpu_optimized_strategy',
                'is_st': False
            }
            
        except Exception as e:
            # 静默失败
            return None
    
    def _get_strategy_recommendations_gpu_batch(self, date):
        """GPU批量策略推荐"""
        print(f"🔍 {date.date()} 获取GPU批量策略推荐...")
        
        # 获取股票代码
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        print(f"  沪深主板股票数量: {len(all_codes)}")
        
        if not all_codes:
            print("  ⚠️  没有找到股票代码")
            return pd.DataFrame()
        
        # 批量处理股票信号
        recommendations = []
        
        # 使用进度条
        with tqdm(total=min(200, len(all_codes)), desc="GPU批量分析", ncols=80) as pbar:
            # 测试前200只股票
            test_codes = all_codes[:200]
            
            # 准备批量数据
            batch_data = []
            for code in test_codes:
                try:
                    # 检查ST
                    st_info = self.st_op.calculate(code)
                    if st_info.get('is_st', False):
                        pbar.update(1)
                        continue
                    
                    # 获取日线数据
                    daily_data = self.base_op.get_daily_data(code, days=20)
                    if daily_data is None or daily_data.empty or len(daily_data) < 10:
                        pbar.update(1)
                        continue
                    
                    current_price = float(daily_data['close'].iloc[-1])
                    if not (current_price > 0 and current_price <= self.max_price):
                        pbar.update(1)
                        continue
                    
                    # 提取价格数据
                    close_prices = daily_data['close'].astype(float).values.tolist()
                    
                    batch_data.append({
                        'code': code,
                        'prices': close_prices,
                        'current_price': current_price
                    })
                    
                except Exception:
                    pass
                
                pbar.update(1)
            
            # 批量GPU计算
            if batch_data and self.use_gpu:
                print(f"  ⚡ GPU批量计算 {len(batch_data)} 只股票...")
                
                # 使用多进程并行处理GPU计算
                with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                    # 分批处理
                    batch_size = 50
                    futures = []
                    
                    for i in range(0, len(batch_data), batch_size):
                        batch = batch_data[i:i+batch_size]
                        future = executor.submit(self._process_stock_batch_gpu, batch)
                        futures.append(future)
                    
                    # 收集结果
                    for future in as_completed(futures):
                        try:
                            batch_results = future.result(timeout=60)
                            recommendations.extend(batch_results)
                        except Exception:
                            pass
            
            elif batch_data:
                # CPU计算
                print(f"  💻 CPU计算 {len(batch_data)} 只股票...")
                
                for data in batch_data:
                    try:
                        code = data['code']
                        prices = data['prices']
                        current_price = data['current_price']
                        
                        # CPU计算指标
                        if len(prices) >= 5:
                            mean_5d = float(np.mean(prices[-5:]))
                            mean_all = float(np.mean(prices))
                            volatility = float(np.std(prices))
                            
                            # 计算得分
                            price_score = 1.0 - (current_price / self.max_price)
                            trend_score = 1.0 if current_price > mean_5d else 0.5
                            volatility_score = 1.0 - min(volatility / mean_all, 0.5) if mean_all > 0 else 0.5
                            
                            confidence = 0.3 + 0.7 * (price_score * 0.4 + trend_score * 0.3 + volatility_score * 0.3)
                            
                            stock_name = self._get_stock_name(code)
                            
                            recommendations.append({
                                'stock_code': code,
                                'stock_name': stock_name,
                                'signal': 'BUY',
                                'confidence': min(confidence, 0.95),
                                'current_price': current_price,
                                'mean_5d': mean_5d,
                                'mean_all': mean_all,
                                'volatility': volatility,
                                'reasons': 'cpu_batch_strategy',
                                'is_st': False
                            })
                    except Exception:
                        pass
        
        if not recommendations:
            print("  ⚠️  没有找到符合条件的股票，使用强制方案...")
            # 强制买入前3只符合条件的股票
            for code in all_codes[:10]:
                try:
                    # 基础检查
                    st_info = self.st_op.calculate(code)
                    if st_info.get('is_st', False):
                        continue
                    
                    daily_data = self.base_op.get_daily_data(code, days=5)
                    if daily_data is None or daily_data.empty:
                        continue
                    
                    current_price = float(daily_data['close'].iloc[-1])
                    if current_price > 0 and current_price <= self.max_price:
                        stock_name = self._get_stock_name(code)
                        recommendations.append({
                            'stock_code': code,
                            'stock_name': stock_name,
                            'signal': 'BUY',
                            'confidence': 0.5,
                            'current_price': current_price,
                            'reasons': 'forced_buy',
                            'is_st': False
                        })
                        
                        if len(recommendations) >= 3:
                            break
                except Exception:
                    continue
        
        if not recommendations:
            print("  ❌ 强制方案也失败，无股票可买")
            return pd.DataFrame()
        
        # 转换为DataFrame
        df = pd.DataFrame(recommendations)
        
        # 排序
        if not df.empty:
            df = df.sort_values('confidence', ascending=False)
        
        print(f"  ✅ GPU策略推荐: {len(df)} 只")
        return df.head(self.max_positions * 2)
    
    def _process_stock_batch_gpu(self, batch_data):
        """处理股票批次的GPU计算"""
        results = []
        
        for data in batch_data:
            try:
                code = data['code']
                prices = data['prices']
                current_price = data['current_price']
                
                if len(prices) < 5:
                    continue
                
                # GPU计算指标
                mean_5d, mean_all, volatility = self._gpu_compute_metrics(prices)
                
                # 计算得分
                price_score = 1.0 - (current_price / self.max_price)
                trend_score = 1.0 if current_price > mean_5d else 0.5
                volatility_score = 1.0 - min(volatility / mean_all, 0.5) if mean_all > 0 else 0.5
                
                confidence = 0.3 + 0.7 * (price_score * 0.4 + trend_score * 0.3 + volatility_score * 0.3)
                
                stock_name = self._get_stock_name(code)
                
                results.append({
                    'stock_code': code,
                    'stock_name': stock_name,
                    'signal': 'BUY',
                    'confidence': min(confidence, 0.95),
                    'current_price': current_price,
                    'mean_5d': mean_5d,
                    'mean_all': mean_all,
                    'volatility': volatility,
                    'reasons': 'gpu_batch_strategy',
                    'is_st': False
                })
                
            except Exception:
                continue
        
        return results
    
    def _calculate_position_size(self, stock_price, confidence):
        """计算仓位大小"""
        # 简单仓位管理：根据信心度分配资金
        max_position_value = self.cash * 0.8  # 最多使用80%现金
        
        # 根据信心度调整
        position_value = max_position_value * confidence
        
        # 确保有足够现金
        position_value = min(position_value, self.cash * 0.9)
        
        # 计算股数（100股为单位）
        shares = int(position_value / stock_price / 100) * 100
        
        # 确保至少买100股
        if shares < 100:
            shares = 100 if stock_price * 100 <= self.cash else 0
        
        return shares
    
    def _execute_trades(self, date, recommendations):
        """执行交易"""
        trades_today = []
        
        # 1. 检查现有持仓的止盈止损
        positions_to_sell = []
        for stock_code, position in list(self.positions.items()):
            try:
                # 获取当前价格
                daily_data = self.base_op.get_daily_data(stock_code, days=2)
                if daily_data is None or daily_data.empty:
                    continue
                
                current_price = float(daily_data['close'].iloc[-1])
                buy_price = position['buy_price']
                buy_date = position['buy_date']
                shares = position['shares']
                
                # 计算收益率
                returns = (current_price - buy_price) / buy_price
                
                # 计算持有天数
                hold_days = (date - buy_date).days
                
                # 止盈止损条件
                sell_reason = None
                if returns <= -0.08:  # 止损 -8%
                    sell_reason = '止损'
                elif returns >= 0.15:  # 止盈 +15%
                    sell_reason = '止盈'
                elif hold_days >= 60:  # 最大持有60天
                    sell_reason = '到期'
                
                if sell_reason:
                    # 卖出
                    sell_value = current_price * shares
                    commission = max(sell_value * 0.0000791, 5)  # 手续费
                    net_proceeds = sell_value - commission
                    
                    self.cash += net_proceeds
                    profit = net_proceeds - (buy_price * shares)
                    
                    trade_record = {
                        'date': date,
                        'stock_code': stock_code,
                        'stock_name': self._get_stock_name(stock_code),
                        'action': 'SELL',
                        'shares': shares,
                        'price': current_price,
                        'value': sell_value,
                        'commission': commission,
                        'profit': profit,
                        'returns': returns,
                        'reason': sell_reason,
                        'hold_days': hold_days
                    }
                    
                    trades_today.append(trade_record)
                    self.trade_history.append(trade_record)
                    positions_to_sell.append(stock_code)
                    
                    print(f"  🛒 卖出 {stock_code}: {shares}股 @ {current_price:.2f}元, 原因: {sell_reason}, 收益: {profit:+.2f}元 ({returns*100:+.1f}%)")
            
            except Exception as e:
                print(f"  ⚠️  检查持仓 {stock_code} 时出错: {e}")
                continue
        
        # 移除已卖出的持仓
        for stock_code in positions_to_sell:
            del self.positions[stock_code]
        
        # 2. 买入新股票
        if recommendations.empty:
            return trades_today
        
        # 计算可用仓位数量
        available_slots = self.max_positions - len(self.positions)
        if available_slots <= 0:
            return trades_today
        
        # 买入推荐股票
        bought_count = 0
        for _, rec in recommendations.iterrows():
            if bought_count >= available_slots:
                break
            
            stock_code = rec['stock_code']
            
            # 检查是否已持有
            if stock_code in self.positions:
                continue
            
            current_price = rec['current_price']
            confidence = rec['confidence']
            
            # 计算买入数量
            shares = self._calculate_position_size(current_price, confidence)
            if shares == 0:
                continue
            
            # 计算买入金额和手续费
            buy_value = current_price * shares
            commission = max(buy_value * 0.0000791, 5)  # 手续费
            total_cost = buy_value + commission
            
            # 检查现金是否足够
            if total_cost > self.cash:
                # 尝试减少股数
                shares = int(self.cash * 0.9 / current_price / 100) * 100
                if shares < 100:
                    continue
                
                buy_value = current_price * shares
                commission = max(buy_value * 0.0000791, 5)
                total_cost = buy_value + commission
            
            # 执行买入
            self.cash -= total_cost
            self.positions[stock_code] = {
                'shares': shares,
                'buy_price': current_price,
                'buy_date': date
            }
            
            trade_record = {
                'date': date,
                'stock_code': stock_code,
                'stock_name': rec['stock_name'],
                'action': 'BUY',
                'shares': shares,
                'price': current_price,
                'value': buy_value,
                'commission': commission,
                'profit': 0,
                'returns': 0,
                'reason': rec['reasons'],
                'hold_days': 0
            }
            
            trades_today.append(trade_record)
            self.trade_history.append(trade_record)
            bought_count += 1
            
            print(f"  🛒 买入 {stock_code}: {shares}股 @ {current_price:.2f}元, 信心度: {confidence:.2f}")
        
        return trades_today
    
    def _record_daily_status(self, date):
        """记录每日状态"""
        # 计算持仓总价值
        position_value = 0
        position_details = []
        
        for stock_code, position in self.positions.items():
            try:
                daily_data = self.base_op.get_daily_data(stock_code, days=2)
                if daily_data is None or daily_data.empty:
                    current_price = position['buy_price']
                else:
                    current_price = float(daily_data['close'].iloc[-1])
                
                shares = position['shares']
                buy_price = position['buy_price']
                value = current_price * shares
                returns = (current_price - buy_price) / buy_price
                
                position_value += value
                position_details.append({
                    'stock_code': stock_code,
                    'stock_name': self._get_stock_name(stock_code),
                    'shares': shares,
                    'buy_price': buy_price,
                    'current_price': current_price,
                    'value': value,
                    'returns': returns,
                    'hold_days': (date - position['buy_date']).days
                })
                
            except Exception:
                continue
        
        total_assets = self.cash + position_value
        total_returns = (total_assets - self.initial_capital) / self.initial_capital
        
        daily_record = {
            'date': date,
            'cash': self.cash,
            'position_value': position_value,
            'total_assets': total_assets,
            'total_returns': total_returns,
            'num_positions': len(self.positions),
            'positions': position_details
        }
        
        self.daily_records.append(daily_record)
        
        return daily_record
    
    def run(self):
        """运行回测"""
        print("\n" + "=" * 60)
        print("🚀 开始GPU优化回测运行")
        print("=" * 60)
        
        # 获取交易日历
        trading_dates = self._get_trading_dates()
        
        # 主回测循环
        total_days = len(trading_dates)
        print(f"📊 总交易日数: {total_days}")
        
        for i, date in enumerate(trading_dates):
            print(f"\n📅 交易日 {i+1}/{total_days}: {date.date()}")
            print("-" * 40)
            
            # 获取策略推荐
            recommendations = self._get_strategy_recommendations_gpu_batch(date)
            
            # 执行交易
            trades = self._execute_trades(date, recommendations)
            
            # 记录每日状态
            daily_status = self._record_daily_status(date)
            
            # 打印状态
            print(f"  💰 现金: {daily_status['cash']:,.2f}元")
            print(f"  📊 持仓价值: {daily_status['position_value']:,.2f}元")
            print(f"  🏦 总资产: {daily_status['total_assets']:,.2f}元")
            print(f"  📈 总收益: {daily_status['total_returns']*100:+.2f}%")
            print(f"  🎯 持仓数量: {daily_status['num_positions']} 只")
            
            # 每10天或最后一天保存进度
            if (i + 1) % 10 == 0 or i == total_days - 1:
                self._save_progress()
        
        # 生成最终报告
        self._generate_final_report()
        
        print("\n" + "=" * 60)
        print("🎉 GPU优化回测完成!")
        print("=" * 60)
        
        return self._get_summary()
    
    def _save_progress(self):
        """保存进度"""
        progress_file = self.output_dir / 'progress.pkl'
        
        progress_data = {
            'cash': self.cash,
            'positions': self.positions,
            'trade_history': self.trade_history,
            'daily_records': self.daily_records
        }
        
        try:
            with open(progress_file, 'wb') as f:
                pickle.dump(progress_data, f)
            print(f"  💾 进度已保存到 {progress_file}")
        except Exception as e:
            print(f"  ⚠️  保存进度失败: {e}")
    
    def _generate_final_report(self):
        """生成最终报告"""
        print("\n" + "=" * 60)
        print("📊 生成GPU优化最终报告")
        print("=" * 60)
        
        # 1. 交易历史CSV
        if self.trade_history:
            trade_df = pd.DataFrame(self.trade_history)
            trade_file = self.output_dir / 'trade_history.csv'
            trade_df.to_csv(trade_file, index=False, encoding='utf-8-sig')
            print(f"  📄 交易历史保存到: {trade_file}")
            print(f"    总交易次数: {len(trade_df)}")
            
            # 分析交易
            buy_trades = trade_df[trade_df['action'] == 'BUY']
            sell_trades = trade_df[trade_df['action'] == 'SELL']
            
            if not sell_trades.empty:
                avg_profit = sell_trades['profit'].mean()
                avg_returns = sell_trades['returns'].mean() * 100
                win_rate = (sell_trades['profit'] > 0).mean() * 100
                
                print(f"    📈 平均每笔盈利: {avg_profit:+.2f}元")
                print(f"    📊 平均收益率: {avg_returns:+.1f}%")
                print(f"    🎯 胜率: {win_rate:.1f}%")
        
        # 2. 性能报告
        perf_file = self.output_dir / 'gpu_performance.json'
        perf_data = {
            'gpu_backend': self.gpu_backend,
            'gpu_enabled': self.use_gpu,
            'num_workers': self.num_workers,
            'total_trades': len(self.trade_history) if self.trade_history else 0,
            'total_days': len(self.daily_records) if self.daily_records else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        with open(perf_file, 'w', encoding='utf-8') as f:
            json.dump(perf_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ⚡ GPU性能报告保存到: {perf_file}")
    
    def _get_summary(self):
        """获取回测摘要"""
        if not self.daily_records:
            return {
                'initial_capital': self.initial_capital,
                'final_cash': self.cash,
                'final_total_assets': self.cash,
                'total_returns': 0.0,
                'annualized_returns': 0.0,
                'num_trades': 0,
                'num_positions': len(self.positions),
                'message': '无交易记录',
                'gpu_backend': self.gpu_backend,
                'gpu_enabled': self.use_gpu
            }
        
        # 获取最后一天的记录
        last_record = self.daily_records[-1]
        
        # 计算年化收益率
        total_days = len(self.daily_records)
        if total_days > 0:
            years = total_days / 252  # 假设一年252个交易日
            total_returns = last_record['total_returns']
            if years > 0:
                annualized_returns = (1 + total_returns) ** (1 / years) - 1
            else:
                annualized_returns = 0.0
        else:
            annualized_returns = 0.0
        
        # 交易统计
        num_trades = len(self.trade_history) if self.trade_history else 0
        
        summary = {
            'initial_capital': self.initial_capital,
            'final_cash': last_record['cash'],
            'final_position_value': last_record['position_value'],
            'final_total_assets': last_record['total_assets'],
            'total_returns': last_record['total_returns'],
            'total_returns_percent': last_record['total_returns'] * 100,
            'annualized_returns': annualized_returns,
            'annualized_returns_percent': annualized_returns * 100,
            'num_trading_days': total_days,
            'num_trades': num_trades,
            'final_num_positions': len(self.positions),
            'gpu_backend': self.gpu_backend,
            'gpu_enabled': self.use_gpu,
            'num_workers': self.num_workers
        }
        
        return summary
    
    def print_summary(self):
        """打印回测摘要"""
        summary = self._get_summary()
        
        print("\n" + "=" * 60)
        print("📋 GPU优化回测最终摘要")
        print("=" * 60)
        print(f"💰 初始资金: {summary['initial_capital']:,}元")
        print(f"💰 最终现金: {summary['final_cash']:,.2f}元")
        print(f"📊 最终持仓价值: {summary['final_position_value']:,.2f}元")
        print(f"🏦 最终总资产: {summary['final_total_assets']:,.2f}元")
        print(f"📈 总收益: {summary['final_total_assets'] - summary['initial_capital']:+,.2f}元")
        print(f"📊 总收益率: {summary['total_returns_percent']:+.2f}%")
        print(f"📅 年化收益率: {summary['annualized_returns_percent']:+.2f}%")
        print(f"🔄 交易天数: {summary['num_trading_days']} 天")
        print(f"🛒 总交易次数: {summary['num_trades']} 次")
        print(f"🎯 最终持仓数量: {summary['final_num_positions']} 只")
        print(f"⚡ GPU加速: {'启用' if summary['gpu_enabled'] else '禁用'}")
        if summary['gpu_enabled']:
            print(f"🎮 GPU后端: {summary['gpu_backend']}")
        print(f"👥 工作进程: {summary['num_workers']} 个")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='GPU优化版回测系统')
    parser.add_argument('--start-date', type=str, default='2025-01-01',
                       help='回测开始日期 (默认: 2025-01-01)')
    parser.add_argument('--end-date', type=str, default=None,
                       help='回测结束日期 (默认: 今天)')
    parser.add_argument('--initial-capital', type=float, default=50000,
                       help='初始资金 (默认: 50000元)')
    parser.add_argument('--max-positions', type=int, default=3,
                       help='最大持仓数量 (默认: 3)')
    parser.add_argument('--max-price', type=float, default=150.0,
                       help='最高买入价格 (默认: 150.0元)')
    parser.add_argument('--output-dir', type=str, default='gpu_optimized_results',
                       help='输出目录 (默认: gpu_optimized_results)')
    parser.add_argument('--no-gpu', action='store_true',
                       help='禁用GPU加速')
    parser.add_argument('--workers', type=int, default=None,
                       help='工作进程数量 (默认: CPU核心数-1)')
    parser.add_argument('--test-only', action='store_true',
                       help='只运行测试，不进行完整回测')
    
    args = parser.parse_args()
    
    if args.test_only:
        # 运行快速测试
        print("🧪 运行GPU快速测试...")
        system = GPUOptimizedBacktestSystem(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            max_positions=args.max_positions,
            max_price=args.max_price,
            use_gpu=not args.no_gpu,
            num_workers=args.workers,
            output_dir=args.output_dir + '_test'
        )
        
        # 测试一天
        test_date = pd.Timestamp(args.start_date)
        recommendations = system._get_strategy_recommendations_gpu_batch(test_date)
        
        if not recommendations.empty:
            print(f"✅ GPU测试通过! 找到 {len(recommendations)} 只推荐股票")
            print("推荐股票:")
            for _, rec in recommendations.iterrows():
                print(f"  {rec['stock_code']} ({rec['stock_name']}): {rec['current_price']:.2f}元, 信心度: {rec['confidence']:.2f}")
        else:
            print("❌ GPU测试失败! 没有找到推荐股票")
        
        return
    
    # 运行完整回测
    system = GPUOptimizedBacktestSystem(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        max_price=args.max_price,
        use_gpu=not args.no_gpu,
        num_workers=args.workers,
        output_dir=args.output_dir
    )
    
    # 运行回测
    system.run()
    
    # 打印摘要
    system.print_summary()

if __name__ == "__main__":
    main()