#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
单线程/单进程回测系统
专门解决baostock多进程访问限制问题
支持灵活并发控制：单线程、多线程、多进程模式
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

class SingleThreadBacktestSystem:
    """单线程/单进程回测系统"""
    
    def __init__(self, start_date='2025-01-01', end_date=None,
                 initial_capital=50000, max_positions=3, max_price=150.0,
                 concurrency_mode='single',  # 'single', 'thread', 'process'
                 num_workers=1, output_dir='single_thread_results'):
        """
        初始化回测系统
        
        Args:
            start_date: 回测开始日期
            end_date: 回测结束日期 (默认今天)
            initial_capital: 初始资金
            max_positions: 最大持仓数量
            max_price: 最高买入价格
            concurrency_mode: 并发模式
                - 'single': 单线程模式（避免baostock限制）
                - 'thread': 多线程模式
                - 'process': 多进程模式
            num_workers: 工作进程/线程数量
            output_dir: 输出目录
        """
        self.start_date = pd.Timestamp(start_date)
        self.end_date = pd.Timestamp(end_date) if end_date else pd.Timestamp.now()
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_price = max_price
        self.concurrency_mode = concurrency_mode
        self.num_workers = num_workers
        self.output_dir = Path(output_dir)
        
        # 根据并发模式调整工作进程数量
        if concurrency_mode == 'single':
            self.num_workers = 1
        elif concurrency_mode == 'thread':
            self.num_workers = min(num_workers, 10)  # 限制线程数量
        elif concurrency_mode == 'process':
            self.num_workers = min(num_workers, mp.cpu_count())
        
        # 初始化操作器
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()
        
        # 持仓和资金
        self.cash = initial_capital
        self.positions = {}  # {stock_code: {'shares': int, 'buy_price': float, 'buy_date': date}}
        self.trade_history = []
        self.daily_records = []
        
        # 创建输出目录
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        print("=" * 60)
        print("🚀 单线程/单进程回测系统启动")
        print("=" * 60)
        print(f"📅 回测期间: {self.start_date.date()} 到 {self.end_date.date()}")
        print(f"💰 初始资金: {self.initial_capital:,}元")
        print(f"📊 最大持仓: {self.max_positions} 只")
        print(f"💵 最高买入价: {self.max_price}元")
        print(f"⚙️  并发模式: {self._get_concurrency_mode_name()}")
        print(f"👥 工作数量: {self.num_workers} 个")
        print("=" * 60)
    
    def _get_concurrency_mode_name(self):
        """获取并发模式名称"""
        names = {
            'single': '单线程模式（避免baostock限制）',
            'thread': '多线程模式',
            'process': '多进程模式'
        }
        return names.get(self.concurrency_mode, self.concurrency_mode)
    
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
    
    def _calculate_stock_signals_simple(self, stock_code):
        """计算单只股票的策略信号（简单版）"""
        try:
            # 检查ST
            st_info = self.st_op.calculate(stock_code)
            is_st = st_info.get('is_st', False)
            if is_st:
                return None
            
            # 获取日线数据
            daily_data = self.base_op.get_daily_data(stock_code, days=10)
            if daily_data is None or daily_data.empty or len(daily_data) < 5:
                return None
            
            current_price = float(daily_data['close'].iloc[-1])
            if not (current_price > 0):
                return None
            
            # 价格限制
            if current_price > self.max_price:
                return None
            
            # 获取股票名称
            stock_name = self._get_stock_name(stock_code)
            
            # 计算简单指标
            close_prices = daily_data['close'].astype(float).values
            
            mean_5d = float(np.mean(close_prices[-5:]))
            mean_all = float(np.mean(close_prices))
            volatility = float(np.std(close_prices))
            
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
                'reasons': 'simple_strategy',
                'is_st': False
            }
            
        except Exception as e:
            # 静默失败
            return None
    
    def _get_strategy_recommendations(self, date):
        """获取策略推荐（支持不同并发模式）"""
        print(f"🔍 {date.date()} 获取策略推荐...")
        
        # 获取股票代码
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        print(f"  沪深主板股票数量: {len(all_codes)}")
        
        if not all_codes:
            print("  ⚠️  没有找到股票代码")
            return pd.DataFrame()
        
        recommendations = []
        
        # 根据并发模式选择不同的处理方式
        if self.concurrency_mode == 'single':
            # 单线程模式（避免baostock限制）
            print(f"  🐌 单线程模式处理前 {min(50, len(all_codes))} 只股票...")
            
            for code in tqdm(all_codes[:50], desc="分析股票", ncols=80):
                try:
                    signal = self._calculate_stock_signals_simple(code)
                    if signal:
                        recommendations.append(signal)
                except Exception:
                    continue
        
        elif self.concurrency_mode == 'thread':
            # 多线程模式
            print(f"  🧵 多线程模式处理前 {min(100, len(all_codes))} 只股票...")
            
            with ThreadPoolExecutor(max_workers=self.num_workers) as executor:
                future_to_code = {executor.submit(self._calculate_stock_signals_simple, code): code 
                                 for code in all_codes[:100]}
                
                for future in as_completed(future_to_code):
                    try:
                        signal = future.result(timeout=30)
                        if signal:
                            recommendations.append(signal)
                    except Exception:
                        continue
        
        elif self.concurrency_mode == 'process':
            # 多进程模式
            print(f"  ⚙️  多进程模式处理前 {min(100, len(all_codes))} 只股票...")
            
            with ProcessPoolExecutor(max_workers=self.num_workers) as executor:
                future_to_code = {executor.submit(self._calculate_stock_signals_simple, code): code 
                                 for code in all_codes[:100]}
                
                for future in as_completed(future_to_code):
                    try:
                        signal = future.result(timeout=30)
                        if signal:
                            recommendations.append(signal)
                    except Exception:
                        continue
        
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
        
        print(f"  ✅ 策略推荐: {len(df)} 只")
        return df.head(self.max_positions * 2)
    
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
        print("🚀 开始回测运行")
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
            recommendations = self._get_strategy_recommendations(date)
            
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
        print("🎉 回测完成!")
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
        print("📊 生成最终报告")
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
        
        # 2. 每日记录CSV
        if self.daily_records:
            daily_df = pd.DataFrame(self.daily_records)
            daily_file = self.output_dir / 'daily_records.csv'
            
            # 简化每日记录
            simple_daily = []
            for record in self.daily_records:
                simple_record = {
                    'date': record['date'],
                    'cash': record['cash'],
                    'position_value': record['position_value'],
                    'total_assets': record['total_assets'],
                    'total_returns': record['total_returns'],
                    'num_positions': record['num_positions']
                }
                simple_daily.append(simple_record)
            
            simple_df = pd.DataFrame(simple_daily)
            simple_df.to_csv(daily_file, index=False, encoding='utf-8-sig')
            print(f"  📅 每日记录保存到: {daily_file}")
        
        # 3. 最终摘要JSON
        summary = self._get_summary()
        summary_file = self.output_dir / 'final_summary.json'
        
        with open(summary_file, 'w', encoding='utf-8') as f:
            json.dump(summary, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"  📋 最终摘要保存到: {summary_file}")
    
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
                'concurrency_mode': self.concurrency_mode,
                'num_workers': self.num_workers
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
            'concurrency_mode': self.concurrency_mode,
            'num_workers': self.num_workers
        }
        
        return summary
    
    def print_summary(self):
        """打印回测摘要"""
        summary = self._get_summary()
        
        print("\n" + "=" * 60)
        print("📋 回测最终摘要")
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
        print(f"⚙️  并发模式: {summary['concurrency_mode']}")
        print(f"👥 工作数量: {summary['num_workers']} 个")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(description='单线程/单进程回测系统')
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
    parser.add_argument('--mode', type=str, default='single',
                       choices=['single', 'thread', 'process'],
                       help='并发模式: single(单线程), thread(多线程), process(多进程) (默认: single)')
    parser.add_argument('--workers', type=int, default=1,
                       help='工作进程/线程数量 (默认: 1)')
    parser.add_argument('--output-dir', type=str, default='single_thread_results',
                       help='输出目录 (默认: single_thread_results)')
    parser.add_argument('--test-only', action='store_true',
                       help='只运行测试，不进行完整回测')
    
    args = parser.parse_args()
    
    if args.test_only:
        # 运行快速测试
        print("🧪 运行单线程模式测试...")
        system = SingleThreadBacktestSystem(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            max_positions=args.max_positions,
            max_price=args.max_price,
            concurrency_mode=args.mode,
            num_workers=args.workers,
            output_dir=args.output_dir + '_test'
        )
        
        # 测试一天
        test_date = pd.Timestamp(args.start_date)
        recommendations = system._get_strategy_recommendations(test_date)
        
        if not recommendations.empty:
            print(f"✅ 测试通过! 找到 {len(recommendations)} 只推荐股票")
            print("推荐股票:")
            for _, rec in recommendations.iterrows():
                print(f"  {rec['stock_code']} ({rec['stock_name']}): {rec['current_price']:.2f}元, 信心度: {rec['confidence']:.2f}")
        else:
            print("❌ 测试失败! 没有找到推荐股票")
        
        return
    
    # 运行完整回测
    system = SingleThreadBacktestSystem(
        start_date=args.start_date,
        end_date=args.end_date,
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        max_price=args.max_price,
        concurrency_mode=args.mode,
        num_workers=args.workers,
        output_dir=args.output_dir
    )
    
    # 运行回测
    system.run()
    
    # 打印摘要
    system.print_summary()

if __name__ == "__main__":
    main()