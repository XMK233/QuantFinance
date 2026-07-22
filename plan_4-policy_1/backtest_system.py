#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略回测系统
基于 weekly_mean_down 和 cross_ma50 策略组合的回测
"""

import argparse
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
from tqdm import tqdm
import warnings
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

class BacktestSystem:
    """策略回测系统"""
    
    def __init__(self, initial_capital=INITIAL_CAPITAL, max_positions=MAX_POSITIONS, 
                 max_price=MAX_PRICE, start_date=START_DATE):
        self.initial_capital = initial_capital
        self.max_positions = max_positions
        self.max_price = max_price
        self.start_date = pd.to_datetime(start_date)
        
        # 数据操作器
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()
        
        # 回测状态
        self.cash = initial_capital
        self.positions = {}  # {stock_code: {'shares': int, 'buy_price': float, 'buy_date': datetime}}
        self.trade_history = []
        self.daily_records = []
        
        # 获取交易日历
        self.trading_dates = self._get_trading_dates()
        
    def _get_trading_dates(self):
        """获取交易日历"""
        print("📅 获取交易日历...")
        
        # 获取所有股票代码来获取交易日历
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        
        # 获取第一只股票的日线数据来获取交易日历
        if all_codes:
            sample_code = all_codes[0]
            daily_data = self.base_op.get_daily_data(sample_code, days=1000)
            if daily_data is not None and not daily_data.empty:
                trading_dates = pd.to_datetime(daily_data['date']).sort_values()
                # 过滤出从开始日期到现在的日期
                trading_dates = trading_dates[trading_dates >= self.start_date]
                trading_dates = trading_dates[trading_dates <= pd.Timestamp.now()]
                return trading_dates.unique()
        
        # 如果无法获取，生成工作日历
        print("⚠️  无法从数据获取交易日历，使用工作日历")
        end_date = pd.Timestamp.now()
        date_range = pd.date_range(start=self.start_date, end=end_date, freq='B')
        return date_range
    
    def _get_strategy_recommendations(self, date):
        """获取当日的策略推荐股票"""
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        recommendations = []

        for stock_code in all_codes:
            try:
                row = self._calculate_combined_signal_asof(stock_code, pd.to_datetime(date))
                if row is not None:
                    recommendations.append(row)
            except Exception:
                continue

        if not recommendations:
            return pd.DataFrame()

        df = pd.DataFrame(recommendations)
        df["score"] = df.apply(self._calculate_stock_score, axis=1)
        df = df.sort_values(["score", "ret_20d", "ret_5d"], ascending=[False, False, False], na_position="last")
        return df.reset_index(drop=True)

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
        try:
            info = self.base_op.get_stock_info(stock_code)
            if isinstance(info, dict):
                return str(info.get("name") or "")
        except Exception:
            return ""
        return ""

    def _calculate_combined_signal_asof(self, stock_code, current_date):
        if self.st_op.calculate(stock_code).get("is_st", False):
            return None

        daily_data = self._get_daily_data_asof(stock_code, current_date, days=30)
        weekly_data = self._get_weekly_data_asof(stock_code, current_date, weeks=70)
        if daily_data is None or daily_data.empty or weekly_data is None or weekly_data.empty:
            return None

        daily_data = daily_data.copy()
        weekly_data = weekly_data.copy()
        for df in (daily_data, weekly_data):
            for col in ["open", "high", "low", "close", "volume", "amount"]:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors="coerce")
        daily_data = daily_data.dropna(subset=["close"])
        weekly_data = weekly_data.dropna(subset=["open", "close"])
        if len(daily_data) < 21 or len(weekly_data) < 60:
            return None

        current_price = float(daily_data["close"].iloc[-1])
        if not (0 < current_price <= self.max_price):
            return None

        for window in [5, 10, 20, 30]:
            weekly_data[f"ma{window}"] = weekly_data["close"].rolling(window=window).mean()

        recent4 = weekly_data.tail(4)
        if recent4.empty:
            return None
        latest_week = recent4.iloc[-1]
        ma_cols = ["ma5", "ma10", "ma20", "ma30"]
        if any(pd.isna(latest_week[c]) for c in ma_cols):
            return None

        cross_ma = bool(
            latest_week["close"] > latest_week["ma5"]
            and latest_week["close"] > latest_week["ma10"]
            and latest_week["close"] > latest_week["ma20"]
            and latest_week["close"] > latest_week["ma30"]
            and latest_week["open"] < latest_week["ma5"]
            and latest_week["open"] < latest_week["ma10"]
            and latest_week["open"] < latest_week["ma20"]
            and latest_week["open"] < latest_week["ma30"]
        )
        if not cross_ma:
            return None

        last60 = weekly_data["close"].tail(60)
        prev30 = last60.iloc[:30]
        recent30 = last60.iloc[30:]
        if prev30.empty or recent30.empty:
            return None
        prev_mean = float(prev30.mean())
        recent_mean = float(recent30.mean())
        if not (prev_mean > 0 and recent_mean > 0 and recent_mean < prev_mean):
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

        return {
            "stock_code": stock_code,
            "stock_name": self._get_stock_name(stock_code),
            "signal": "BUY",
            "confidence": 0.7,
            "current_price": current_price,
            "reasons": "cross_ma50 + weekly_mean_down",
            "cross_ma_4w": True,
            "is_st": False,
            "ret_5d": float(ret_5d) if ret_5d is not None and pd.notna(ret_5d) else None,
            "ret_20d": float(ret_20d) if ret_20d is not None and pd.notna(ret_20d) else None,
            "weekly_mean_0_30": recent_mean,
            "weekly_mean_30_60": prev_mean,
            "weekly_mean_ratio": recent_mean / prev_mean,
        }
    
    def _calculate_position_value(self, stock_code, current_price):
        """计算持仓市值"""
        if stock_code not in self.positions:
            return 0
        
        position = self.positions[stock_code]
        return position['shares'] * current_price
    
    def _calculate_total_value(self, date):
        """计算总资产价值"""
        total_value = self.cash
        
        for stock_code, position in self.positions.items():
            current_price = self._get_price_asof(stock_code, date)
            if current_price is not None:
                total_value += position['shares'] * current_price
        
        return total_value
    
    def _should_sell(self, stock_code, position, current_date, current_price):
        """判断是否应该卖出"""
        buy_price = position['buy_price']
        return_rate = (current_price - buy_price) / buy_price
        if return_rate <= STOP_LOSS_RATE:
            return True, f"止损触发: {return_rate:.1%}"
        return False, ""
    
    def _evaluate_position_performance(self, current_date):
        """评估当前持仓的表现"""
        performance = []
        
        for stock_code, position in self.positions.items():
            current_price = self._get_price_asof(stock_code, current_date)
            if current_price is None:
                continue
            buy_price = position['buy_price']
            buy_date = position['buy_date']
            
            # 计算收益率
            return_rate = (current_price - buy_price) / buy_price
            
            # 计算持有天数
            hold_days = (current_date - buy_date).days
            
            # 计算综合得分（考虑收益率和持有时间）
            # 收益率越高得分越高，持有时间越长得分越低（鼓励换仓）
            score = return_rate * 100 - (hold_days / 30)  # 每持有1个月减1分
            
            performance.append({
                'stock_code': stock_code,
                'stock_name': position.get('stock_name', ''),
                'buy_price': buy_price,
                'current_price': current_price,
                'return_rate': return_rate,
                'hold_days': hold_days,
                'score': score
            })
        
        return performance
    
    def _calculate_stock_score(self, stock_row):
        """计算股票的预期得分"""
        # 基础得分：策略置信度
        base_score = stock_row.get('confidence', 0.5) * 10
        
        # 价格得分：价格越低得分越高（便于资金分配）
        price = stock_row.get('current_price', 0)
        if price > 0:
            price_score = 10 / (price / 10)  # 价格每10元得1分
        else:
            price_score = 0
        
        # 如果有周均价比率，加入得分
        mean_ratio = stock_row.get('weekly_mean_ratio', 1.0)
        if mean_ratio < 1.0:  # 比率小于1表示近期均价更低，得分更高
            ratio_score = (1.0 - mean_ratio) * 20
        else:
            ratio_score = 0
        
        total_score = base_score + price_score + ratio_score
        return total_score
    
    def _execute_sell(self, stock_code, current_date, reason=""):
        """执行卖出操作"""
        if stock_code not in self.positions:
            return
        
        position = self.positions[stock_code]
        sell_price = self._get_price_asof(stock_code, current_date)
        if sell_price is None:
            return
        shares = position['shares']
        
        # 计算卖出金额
        sell_amount = shares * sell_price
        
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
            'price': sell_price,
            'amount': sell_amount,
            'fee': fee,
            'profit': profit,
            'reason': reason
        })
        
        # 移除持仓
        del self.positions[stock_code]
        
        print(f"  📤 卖出 {stock_code}: {shares}股 @ {sell_price:.2f}, 盈利: {profit:.2f}元 ({reason})")
    
    def _execute_buy(self, stock_code, stock_name, current_price, current_date, target_value=TARGET_BUY_VALUE):
        """执行买入操作"""
        budget = min(float(target_value), float(self.cash))
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
    
    def run_backtest(self):
        """运行回测"""
        print(f"🚀 开始策略回测")
        print(f"📊 初始资金: {self.initial_capital:.2f}元")
        print(f"📈 策略组合: cross_ma50 + weekly_mean_down（按回测日历史数据筛选）")
        print(f"📅 回测期间: {self.start_date.date()} 至 {pd.Timestamp.now().date()}")
        print(f"🎯 限制条件: 最多{self.max_positions}只持仓, 单价≤{self.max_price}元, 单票约{TARGET_BUY_VALUE:.0f}元, 止损{abs(STOP_LOSS_RATE):.0%}")
        print("-" * 60)
        
        # 进度条
        pbar = tqdm(self.trading_dates, desc="回测进度", unit="交易日")
        
        for current_date in pbar:
            # 更新进度条描述
            pbar.set_description(f"回测 {current_date.date()}")
            
            # 1. 检查现有持仓是否需要卖出
            positions_to_sell = []
            for stock_code, position in list(self.positions.items()):
                current_price = self._get_price_asof(stock_code, current_date)
                if current_price is None:
                    continue
                should_sell, reason = self._should_sell(
                    stock_code, position, current_date, current_price
                )
                
                if should_sell:
                    positions_to_sell.append((stock_code, reason))
            
            # 执行卖出
            for stock_code, reason in positions_to_sell:
                self._execute_sell(stock_code, current_date, reason)
            
            # 2. 获取当日策略推荐
            recommendations = self._get_strategy_recommendations(current_date)
            
            if not recommendations.empty:
                # 过滤掉已经持有的股票
                recommendations = recommendations[~recommendations['stock_code'].isin(self.positions.keys())]
                
                available_slots = self.max_positions - len(self.positions)
                if available_slots > 0 and self.cash > 1000:
                    for _, row in recommendations.iterrows():
                        if available_slots <= 0:
                            break
                        
                        stock_code = row['stock_code']
                        stock_name = row['stock_name']
                        current_price = row['current_price']
                        
                        # 检查价格限制
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
        
        print("-" * 60)
        print("✅ 回测完成")
        
        return self._generate_results()
    
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
            
            # 获取当前价格
            current_price = self._get_price_asof(stock_code, date)
            if current_price is not None:
                record[f'position_{i}_current_price'] = current_price
                record[f'position_{i}_value'] = position['shares'] * current_price
                record[f'position_{i}_profit'] = position['shares'] * (current_price - position['buy_price'])
            else:
                record[f'position_{i}_current_price'] = position['buy_price']
                record[f'position_{i}_value'] = position['shares'] * position['buy_price']
                record[f'position_{i}_profit'] = 0
        
        return record
    
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
                'final_total_value': self._calculate_total_value(pd.Timestamp.now()) if not daily_df.empty else self.cash
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
                'final_total_value': self.cash
            }
        
        return daily_df, trade_df, stats
    
    def save_results(self, output_dir="backtest_results"):
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
            f.write("策略回测统计报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"回测期间: {self.start_date.date()} 至 {pd.Timestamp.now().date()}\n")
            f.write(f"初始资金: {self.initial_capital:.2f}元\n")
            f.write(f"策略组合: cross_ma50 + weekly_mean_down（按回测日历史数据筛选）\n")
            f.write(f"限制条件: 最多{self.max_positions}只持仓, 单价≤{self.max_price}元, 单票约{TARGET_BUY_VALUE:.0f}元, 止损{abs(STOP_LOSS_RATE):.0%}\n")
            f.write("\n交易统计:\n")
            f.write(f"  总交易次数: {stats['total_trades']}\n")
            f.write(f"  买入交易: {stats['buy_trades']}\n")
            f.write(f"  卖出交易: {stats['sell_trades']}\n")
            f.write(f"  总盈利: {stats['total_profit']:.2f}元\n")
            f.write(f"  胜率: {stats['win_rate']:.1%}\n")
            f.write(f"  平均每笔盈利: {stats['avg_profit_per_trade']:.2f}元\n")
            f.write(f"  最大盈利: {stats['max_profit']:.2f}元\n")
            f.write(f"  最大亏损: {stats['max_loss']:.2f}元\n")
            f.write(f"  最终现金: {stats['final_cash']:.2f}元\n")
            f.write(f"  最终总资产: {stats['final_total_value']:.2f}元\n")
            f.write(f"  总收益率: {(stats['final_total_value'] - self.initial_capital) / self.initial_capital:.1%}\n")
        
        print(f"💾 统计报告已保存: {stats_file}")
        
        return daily_file, trade_file, stats_file

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='策略回测系统')
    parser.add_argument('--start-date', type=str, default=START_DATE, 
                       help=f'回测开始日期 (默认: {START_DATE})')
    parser.add_argument('--initial-capital', type=float, default=INITIAL_CAPITAL,
                       help=f'初始资金 (默认: {INITIAL_CAPITAL})')
    parser.add_argument('--max-positions', type=int, default=MAX_POSITIONS,
                       help=f'最大持仓数量 (默认: {MAX_POSITIONS})')
    parser.add_argument('--max-price', type=float, default=MAX_PRICE,
                       help=f'最高买入价格 (默认: {MAX_PRICE})')
    parser.add_argument('--output-dir', type=str, default='backtest_results',
                       help='输出目录 (默认: backtest_results)')
    
    args = parser.parse_args()
    
    # 创建回测系统
    backtest = BacktestSystem(
        initial_capital=args.initial_capital,
        max_positions=args.max_positions,
        max_price=args.max_price,
        start_date=args.start_date
    )
    
    # 运行回测
    daily_df, trade_df, stats = backtest.run_backtest()
    
    # 保存结果
    backtest.save_results(args.output_dir)
    
    # 打印摘要
    print("\n📊 回测摘要:")
    print(f"  最终总资产: {stats['final_total_value']:.2f}元")
    print(f"  总收益率: {(stats['final_total_value'] - args.initial_capital) / args.initial_capital:.1%}")
    print(f"  总交易次数: {stats['total_trades']}")
    print(f"  胜率: {stats['win_rate']:.1%}")
    print(f"  总盈利: {stats['total_profit']:.2f}元")

if __name__ == "__main__":
    main()
