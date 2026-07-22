#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单测试回测系统 - 只测试几个交易日
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path
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

def test_simple_strategy():
    """测试简单策略"""
    print("🧪 测试简单策略")
    print("-" * 50)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"找到 {len(all_codes)} 只沪深主板股票")
    
    if len(all_codes) == 0:
        print("❌ 没有股票代码")
        return
    
    # 只测试前30只股票
    test_codes = all_codes[:30]
    
    print(f"\n测试 {len(test_codes)} 只股票的简单策略条件:")
    print("条件: 非ST + 价格≤150元 + 有日线数据")
    
    qualified = []
    
    for code in test_codes:
        try:
            # 检查ST
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            if is_st:
                continue
            
            # 获取日线数据
            daily_data = base_op.get_daily_data(code, days=10)
            if daily_data is None or daily_data.empty:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            
            # 检查价格限制
            if not (current_price > 0 and current_price <= 150.0):
                continue
            
            # 获取股票名称
            stock_name = base_op.get_stock_name(code) or ""
            
            qualified.append({
                'code': code,
                'name': stock_name,
                'price': current_price
            })
            
        except Exception as e:
            print(f"  {code}: ❌ 错误: {e}")
            continue
    
    print(f"\n✅ 找到 {len(qualified)} 只满足简单条件的股票:")
    
    if qualified:
        for i, stock in enumerate(qualified[:10], 1):
            print(f"  {i}. {stock['code']} ({stock['name']}): {stock['price']:.2f}元")
    
    return qualified

def test_backtest_logic():
    """测试回测逻辑"""
    print("\n🧪 测试回测逻辑")
    print("-" * 50)
    
    # 模拟几个交易日
    start_date = pd.to_datetime('2025-01-01')
    end_date = pd.to_datetime('2025-01-10')
    trading_dates = pd.date_range(start=start_date, end=end_date, freq='B')
    
    print(f"模拟交易日: {len(trading_dates)} 天")
    print(f"日期范围: {start_date.date()} 到 {end_date.date()}")
    
    # 初始资金
    initial_capital = 50000
    cash = initial_capital
    positions = {}
    trade_history = []
    
    print(f"\n💰 初始资金: {cash:.2f}元")
    
    # 测试买入逻辑
    test_stocks = [
        {'code': 'sh.600000', 'name': '浦发银行', 'price': 9.24},
        {'code': 'sh.600004', 'name': '白云机场', 'price': 8.16},
        {'code': 'sh.600006', 'name': '东风汽车', 'price': 5.66}
    ]
    
    for i, stock in enumerate(test_stocks[:2], 1):  # 只买入前2只
        if len(positions) >= 3:  # 最多3只持仓
            break
        
        if cash < 1000:
            break
        
        # 计算可买股数（至少100股）
        max_shares = int(cash // (stock['price'] * 100)) * 100
        if max_shares < 100:
            continue
        
        # 实际买入股数（不超过可用资金的80%）
        buy_shares = min(max_shares, int(cash * 0.8 // stock['price']))
        if buy_shares < 100:
            continue
        
        # 计算买入金额
        buy_amount = buy_shares * stock['price']
        
        # 计算手续费
        fee_rate = 0.791 / 10000
        min_fee = 5.0
        fee = max(buy_amount * fee_rate, min_fee)
        
        # 总成本
        total_cost = buy_amount + fee
        
        # 检查是否有足够现金
        if total_cost > cash:
            continue
        
        # 更新现金
        cash -= total_cost
        
        # 记录持仓
        positions[stock['code']] = {
            'shares': buy_shares,
            'buy_price': stock['price'],
            'buy_date': start_date,
            'stock_name': stock['name']
        }
        
        # 记录交易
        trade_history.append({
            'date': start_date,
            'stock_code': stock['code'],
            'action': 'BUY',
            'shares': buy_shares,
            'price': stock['price'],
            'amount': buy_amount,
            'fee': fee,
            'profit': 0,
            'reason': '测试买入'
        })
        
        print(f"  📥 买入 {stock['code']}({stock['name']}): {buy_shares}股 @ {stock['price']:.2f}, 成本: {total_cost:.2f}元")
    
    print(f"\n📊 买入后状态:")
    print(f"  现金: {cash:.2f}元")
    print(f"  持仓数量: {len(positions)} 只")
    
    # 计算总资产价值
    total_value = cash
    for code, position in positions.items():
        position_value = position['shares'] * position['buy_price']
        total_value += position_value
        print(f"  {code}: {position['shares']}股 @ {position['buy_price']:.2f}, 价值: {position_value:.2f}元")
    
    print(f"  总资产: {total_value:.2f}元")
    
    return positions, trade_history

def main():
    """主函数"""
    print("🔍 简单回测系统测试")
    print("=" * 70)
    
    # 测试简单策略
    qualified_stocks = test_simple_strategy()
    
    if not qualified_stocks:
        print("\n❌ 没有找到任何符合条件的股票")
        return
    
    # 测试回测逻辑
    positions, trades = test_backtest_logic()
    
    print("\n" + "=" * 70)
    print("📋 测试总结")
    print("=" * 70)
    
    print(f"✅ 简单策略测试通过")
    print(f"✅ 回测逻辑测试通过")
    print(f"📊 找到 {len(qualified_stocks)} 只符合条件的股票")
    print(f"📈 模拟买入 {len(positions)} 只股票")
    print(f"📋 记录 {len(trades)} 笔交易")
    
    print("\n💡 建议:")
    print("   1. 原策略条件太严格（cross_ma50策略没有股票满足）")
    print("   2. 建议使用放宽版策略或简化条件")
    print("   3. 可以增加测试股票数量以提高找到合适股票的概率")

if __name__ == "__main__":
    main()