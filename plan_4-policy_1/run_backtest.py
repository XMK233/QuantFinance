#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
策略回测主运行脚本
整合所有模块，运行完整的回测流程
支持GPU加速选项
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest_system import BacktestSystem
from strategy_combiner import StrategyCombiner
from data_manager import DataManager
from results_exporter import ResultsExporter

# 尝试导入GPU加速版本
try:
    from accelerated_backtest import AcceleratedBacktestSystem
    GPU_AVAILABLE = True
except ImportError:
    GPU_AVAILABLE = False
    print("⚠️  GPU加速版本不可用，将使用原始版本")

def run_full_backtest(start_date='2025-01-01', end_date=None, 
                     initial_capital=50000, max_positions=3, 
                     max_price=150.0, output_dir='backtest_results',
                     use_gpu=False, num_workers=None):
    """
    运行完整的策略回测
    
    Args:
        start_date: 回测开始日期
        end_date: 回测结束日期 (默认今天)
        initial_capital: 初始资金
        max_positions: 最大持仓数量
        max_price: 最高买入价格
        output_dir: 输出目录
        use_gpu: 是否使用GPU加速
        num_workers: 工作进程数量
        
    Returns:
        回测结果字典
    """
    print("=" * 70)
    print("🚀 开始策略回测系统")
    print("=" * 70)
    
    # 设置结束日期
    if end_date is None:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    # 转换日期格式
    start_date_dt = pd.to_datetime(start_date)
    end_date_dt = pd.to_datetime(end_date)
    
    print(f"📅 回测期间: {start_date_dt.date()} 至 {end_date_dt.date()}")
    print(f"💰 初始资金: {initial_capital:,.0f}元")
    print(f"🎯 策略组合: cross_ma50 + weekly_mean_down（按回测日历史数据筛选）")
    print(f"📊 限制条件: 最多{max_positions}只持仓, 单价≤{max_price}元, 单票约15000元, 止损10%")
    
    # 选择回测系统
    if use_gpu and GPU_AVAILABLE:
        print(f"⚡ 加速模式: GPU加速, {num_workers if num_workers else '自动'}个工作进程")
        backtest = AcceleratedBacktestSystem(
            initial_capital=initial_capital,
            max_positions=max_positions,
            max_price=max_price,
            start_date=start_date,
            use_gpu=True,
            num_workers=num_workers
        )
    else:
        if use_gpu and not GPU_AVAILABLE:
            print("⚠️  GPU加速不可用，使用原始版本")
        print(f"⚡ 加速模式: 原始版本")
        backtest = BacktestSystem(
            initial_capital=initial_capital,
            max_positions=max_positions,
            max_price=max_price,
            start_date=start_date
        )
    
    print("-" * 70)
    
    # 运行回测
    print("1️⃣ 运行回测...")
    daily_df, trade_df, stats = backtest.run_backtest()
    
    # 导出结果
    print("2️⃣ 导出结果...")
    exporter = ResultsExporter(output_dir=output_dir)
    
    results = exporter.generate_comprehensive_report(
        daily_df, trade_df, stats, 
        strategy_name='cross_ma50+weekly_mean_down_stoploss10_target15000'
    )
    
    # 打印最终摘要
    print("\n" + "=" * 70)
    print("📋 回测最终摘要")
    print("=" * 70)
    
    if not daily_df.empty:
        initial_value = daily_df['total_value'].iloc[0]
        final_value = daily_df['total_value'].iloc[-1]
        total_return = final_value - initial_value
        return_rate = total_return / initial_value if initial_value > 0 else 0
        
        print(f"💰 初始资金: {initial_value:,.0f}元")
        print(f"💰 最终总资产: {final_value:,.0f}元")
        print(f"📈 总收益: {total_return:+,.0f}元")
        print(f"📊 总收益率: {return_rate:+.1%}")
        
        # 计算年化收益率
        days_held = (end_date_dt - start_date_dt).days
        years_held = days_held / 365.25
        annualized_return = (1 + return_rate) ** (1 / years_held) - 1 if years_held > 0 else 0
        print(f"📅 年化收益率: {annualized_return:+.1%}")
    
    if not trade_df.empty:
        total_trades = len(trade_df)
        buy_trades = len(trade_df[trade_df['action'] == 'BUY'])
        sell_trades = len(trade_df[trade_df['action'] == 'SELL'])
        
        sell_trades_df = trade_df[trade_df['action'] == 'SELL']
        if not sell_trades_df.empty:
            win_trades = len(sell_trades_df[sell_trades_df['profit'] > 0])
            win_rate = win_trades / len(sell_trades_df)
            total_profit = sell_trades_df['profit'].sum()
            
            print(f"\n💹 交易统计:")
            print(f"  总交易次数: {total_trades}")
            print(f"  买入交易: {buy_trades}")
            print(f"  卖出交易: {sell_trades}")
            print(f"  胜率: {win_rate:.1%}")
            print(f"  总盈利: {total_profit:+,.0f}元")
    
    print(f"\n💾 所有结果已保存到: {output_dir}")
    print("=" * 70)
    
    return {
        'daily_df': daily_df,
        'trade_df': trade_df,
        'stats': stats,
        'results_files': results
    }

def run_quick_test():
    """运行快速测试"""
    print("🧪 运行快速测试...")
    
    # 使用最近30天进行快速测试
    end_date = datetime.now()
    start_date = end_date - timedelta(days=60)
    
    results = run_full_backtest(
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        initial_capital=10000,
        max_positions=2,
        max_price=100.0,
        output_dir='quick_test_results'
    )
    
    return results

def analyze_strategy_performance():
    """分析策略表现"""
    print("📊 分析策略表现...")
    
    # 创建策略组合器
    combiner = StrategyCombiner(max_price=150.0)
    
    # 设置分析期间
    start_date = pd.to_datetime('2025-01-01')
    end_date = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    
    # 运行分析
    results = combiner.analyze_strategy_performance(
        start_date=start_date,
        end_date=end_date,
        initial_capital=50000
    )
    
    # 保存结果
    combiner.save_analysis_results(results, 'strategy_analysis')
    
    return results

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='策略回测主运行脚本')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 完整回测命令
    full_parser = subparsers.add_parser('full', help='运行完整回测')
    full_parser.add_argument('--start-date', type=str, default='2025-01-01',
                           help='回测开始日期 (默认: 2025-01-01)')
    full_parser.add_argument('--end-date', type=str, default=None,
                           help='回测结束日期 (默认: 今天)')
    full_parser.add_argument('--initial-capital', type=float, default=50000,
                           help='初始资金 (默认: 50000)')
    full_parser.add_argument('--max-positions', type=int, default=3,
                           help='最大持仓数量 (默认: 3)')
    full_parser.add_argument('--max-price', type=float, default=150.0,
                           help='最高买入价格 (默认: 150.0)')
    full_parser.add_argument('--output-dir', type=str, default='backtest_results',
                           help='输出目录 (默认: backtest_results)')
    full_parser.add_argument('--gpu', action='store_true',
                           help='启用GPU加速 (如果可用)')
    full_parser.add_argument('--workers', type=int, default=None,
                           help='工作进程数量 (默认: CPU核心数-1)')
    
    # 快速测试命令
    test_parser = subparsers.add_parser('test', help='运行快速测试')
    
    # 策略分析命令
    analyze_parser = subparsers.add_parser('analyze', help='分析策略表现')
    
    args = parser.parse_args()
    
    if args.command == 'full':
        run_full_backtest(
            start_date=args.start_date,
            end_date=args.end_date,
            initial_capital=args.initial_capital,
            max_positions=args.max_positions,
            max_price=args.max_price,
            output_dir=args.output_dir,
            use_gpu=args.gpu,
            num_workers=args.workers
        )
    
    elif args.command == 'test':
        run_quick_test()
    
    elif args.command == 'analyze':
        analyze_strategy_performance()
    
    else:
        # 默认运行完整回测
        print("未指定命令，运行完整回测...")
        run_full_backtest()

if __name__ == "__main__":
    main()
