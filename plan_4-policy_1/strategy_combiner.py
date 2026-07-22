#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略组合器
专门用于 weekly_mean_down 和 cross_ma50 策略的组合
"""

import pandas as pd
import numpy as np
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

class StrategyCombiner:
    """策略组合器"""
    
    def __init__(self, max_price=150.0):
        self.max_price = max_price
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()
    
    def get_combined_recommendations(self, date=None, top_n=20):
        """
        获取策略组合推荐
        
        Args:
            date: 日期（可选）
            top_n: 返回前N个推荐
            
        Returns:
            DataFrame with combined recommendations
        """
        print(f"🔍 获取策略组合推荐 (weekly_mean_down + cross_ma50)")
        
        # 获取所有沪深主板股票
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        print(f"  沪深主板股票数量: {len(all_codes)}")
        
        # 第一步：应用 cross_ma50 策略
        print("  1. 应用 cross_ma50 策略...")
        cross_ma_df = generate_cross_ma_strategy_recommendations(
            exclude_gem=True,
            exclude_star=True,
            top_n=100,
            price_cap=self.max_price,
            stock_codes=all_codes
        )
        
        if cross_ma_df.empty:
            print("  ⚠️  cross_ma50 策略无推荐")
            return pd.DataFrame()
        
        print(f"  ✅ cross_ma50 策略推荐: {len(cross_ma_df)} 只")
        
        # 第二步：应用 weekly_mean_down 策略
        print("  2. 应用 weekly_mean_down 策略...")
        weekly_mean_df = generate_weekly_mean_down_strategy_recommendations(
            exclude_gem=True,
            exclude_star=True,
            top_n=100,
            stock_codes=cross_ma_df['stock_code'].tolist()
        )
        
        if weekly_mean_df.empty:
            print("  ⚠️  weekly_mean_down 策略无推荐")
            return pd.DataFrame()
        
        print(f"  ✅ 策略组合推荐: {len(weekly_mean_df)} 只")
        
        # 添加策略标签
        weekly_mean_df['strategy'] = 'weekly_mean_down+cross_ma50'
        
        return weekly_mean_df.head(top_n)
    
    def get_stock_price_history(self, stock_code, start_date, end_date):
        """获取股票价格历史"""
        # 计算天数
        days = (end_date - start_date).days + 30  # 加一些缓冲
        
        daily_data = self.base_op.get_daily_data(stock_code, days=days)
        if daily_data is None or daily_data.empty:
            return pd.DataFrame()
        
        # 转换日期
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        
        # 过滤日期范围
        mask = (daily_data['date'] >= start_date) & (daily_data['date'] <= end_date)
        filtered_data = daily_data[mask].copy()
        
        return filtered_data
    
    def analyze_strategy_performance(self, start_date, end_date, initial_capital=50000):
        """
        分析策略表现
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            initial_capital: 初始资金
            
        Returns:
            策略表现分析结果
        """
        print(f"📊 分析策略表现: {start_date.date()} 至 {end_date.date()}")
        
        # 获取交易日历
        trading_dates = self._get_trading_dates(start_date, end_date)
        
        if len(trading_dates) == 0:
            print("  ⚠️  无交易日数据")
            return {}
        
        # 模拟每日投资
        cash = initial_capital
        positions = {}
        daily_values = []
        
        pbar = tqdm(trading_dates, desc="策略分析进度", unit="交易日")
        
        for current_date in pbar:
            # 获取当日推荐
            recommendations = self.get_combined_recommendations(current_date, top_n=3)
            
            # 更新持仓价值
            total_value = cash
            for stock_code in list(positions.keys()):
                price_data = self.get_stock_price_history(stock_code, current_date, current_date)
                if not price_data.empty:
                    current_price = float(price_data['close'].iloc[-1])
                    positions[stock_code]['current_value'] = positions[stock_code]['shares'] * current_price
                    total_value += positions[stock_code]['current_value']
                else:
                    # 如果没有价格数据，移除持仓
                    del positions[stock_code]
            
            # 记录当日价值
            daily_values.append({
                'date': current_date,
                'cash': cash,
                'positions': len(positions),
                'total_value': total_value
            })
            
            # 如果有空位且有推荐，尝试买入
            if len(positions) < 3 and not recommendations.empty:
                for _, row in recommendations.iterrows():
                    if len(positions) >= 3:
                        break
                    
                    stock_code = row['stock_code']
                    if stock_code in positions:
                        continue
                    
                    current_price = row['current_price']
                    
                    # 计算可买股数
                    max_shares = int(cash // (current_price * 100)) * 100
                    if max_shares >= 100:
                        buy_shares = min(max_shares, int(cash * 0.8 // current_price))
                        
                        if buy_shares >= 100:
                            buy_amount = buy_shares * current_price
                            cash -= buy_amount
                            
                            positions[stock_code] = {
                                'shares': buy_shares,
                                'buy_price': current_price,
                                'buy_date': current_date,
                                'current_value': buy_amount
                            }
            
            pbar.set_description(f"策略分析 {current_date.date()}")
        
        # 计算最终结果
        final_value = daily_values[-1]['total_value'] if daily_values else initial_capital
        total_return = final_value - initial_capital
        return_rate = total_return / initial_capital
        
        # 计算年化收益率
        days_held = (end_date - start_date).days
        years_held = days_held / 365.25
        annualized_return = (1 + return_rate) ** (1 / years_held) - 1 if years_held > 0 else 0
        
        results = {
            'initial_capital': initial_capital,
            'final_value': final_value,
            'total_return': total_return,
            'return_rate': return_rate,
            'annualized_return': annualized_return,
            'trading_days': len(trading_dates),
            'max_positions': 3,
            'max_price': self.max_price,
            'daily_values': pd.DataFrame(daily_values)
        }
        
        print(f"  ✅ 分析完成:")
        print(f"     初始资金: {initial_capital:.2f}元")
        print(f"     最终价值: {final_value:.2f}元")
        print(f"     总收益: {total_return:.2f}元")
        print(f"     收益率: {return_rate:.1%}")
        print(f"     年化收益率: {annualized_return:.1%}")
        
        return results
    
    def _get_trading_dates(self, start_date, end_date):
        """获取交易日历"""
        # 获取样本股票的交易日历
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        
        if not all_codes:
            return []
        
        sample_code = all_codes[0]
        daily_data = self.base_op.get_daily_data(sample_code, days=1000)
        
        if daily_data is None or daily_data.empty:
            # 生成工作日历
            date_range = pd.date_range(start=start_date, end=end_date, freq='B')
            return date_range
        
        # 从数据获取交易日历
        trading_dates = pd.to_datetime(daily_data['date']).sort_values()
        mask = (trading_dates >= start_date) & (trading_dates <= end_date)
        filtered_dates = trading_dates[mask].unique()
        
        return filtered_dates
    
    def save_analysis_results(self, results, output_dir="strategy_analysis"):
        """保存分析结果"""
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 保存每日价值数据
        if 'daily_values' in results and not results['daily_values'].empty:
            daily_file = output_dir / f"daily_values_{timestamp}.csv"
            results['daily_values'].to_csv(daily_file, index=False, encoding='utf-8-sig')
            print(f"💾 每日价值数据已保存: {daily_file}")
        
        # 保存摘要报告
        summary_file = output_dir / f"strategy_summary_{timestamp}.txt"
        with open(summary_file, 'w', encoding='utf-8') as f:
            f.write("策略组合分析报告\n")
            f.write("=" * 50 + "\n")
            f.write(f"策略组合: weekly_mean_down + cross_ma50\n")
            f.write(f"分析时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"最大持仓: {results.get('max_positions', 3)}只\n")
            f.write(f"价格上限: {results.get('max_price', 150.0)}元\n")
            f.write(f"交易日数: {results.get('trading_days', 0)}\n")
            f.write("\n财务表现:\n")
            f.write(f"  初始资金: {results.get('initial_capital', 0):.2f}元\n")
            f.write(f"  最终价值: {results.get('final_value', 0):.2f}元\n")
            f.write(f"  总收益: {results.get('total_return', 0):.2f}元\n")
            f.write(f"  收益率: {results.get('return_rate', 0):.1%}\n")
            f.write(f"  年化收益率: {results.get('annualized_return', 0):.1%}\n")
        
        print(f"💾 策略摘要已保存: {summary_file}")
        
        return daily_file, summary_file

def main():
    """主函数"""
    import argparse
    
    parser = argparse.ArgumentParser(description='策略组合分析')
    parser.add_argument('--start-date', type=str, default='2025-01-01',
                       help='分析开始日期 (默认: 2025-01-01)')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                       help='分析结束日期 (默认: 今天)')
    parser.add_argument('--initial-capital', type=float, default=50000,
                       help='初始资金 (默认: 50000)')
    parser.add_argument('--max-price', type=float, default=150.0,
                       help='最高买入价格 (默认: 150.0)')
    parser.add_argument('--output-dir', type=str, default='strategy_analysis',
                       help='输出目录 (默认: strategy_analysis)')
    
    args = parser.parse_args()
    
    # 创建策略组合器
    combiner = StrategyCombiner(max_price=args.max_price)
    
    # 运行分析
    start_date = pd.to_datetime(args.start_date)
    end_date = pd.to_datetime(args.end_date)
    
    results = combiner.analyze_strategy_performance(
        start_date=start_date,
        end_date=end_date,
        initial_capital=args.initial_capital
    )
    
    # 保存结果
    combiner.save_analysis_results(results, args.output_dir)

if __name__ == "__main__":
    main()