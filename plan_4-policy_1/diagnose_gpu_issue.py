#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
诊断GPU加速回测系统为什么没有交易
"""

import pandas as pd
import numpy as np
from datetime import datetime
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

def test_data_availability():
    """测试数据可用性"""
    print("🧪 测试数据可用性")
    print("-" * 50)
    
    base_op = BaseOperator()
    
    # 1. 测试获取股票代码
    print("1️⃣ 获取沪深主板股票代码...")
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"   找到 {len(all_codes)} 只沪深主板股票")
    
    if len(all_codes) == 0:
        print("   ❌ 没有找到任何股票代码")
        return False
    
    # 2. 测试获取前10只股票的日线数据
    print("\n2️⃣ 测试前10只股票的日线数据...")
    test_codes = all_codes[:10]
    
    for i, code in enumerate(test_codes, 1):
        print(f"   {i}. {code}: ", end="")
        try:
            daily_data = base_op.get_daily_data(code, days=30)
            if daily_data is None or daily_data.empty:
                print("❌ 无数据")
            else:
                print(f"✅ {len(daily_data)} 天数据")
                if not daily_data.empty:
                    current_price = float(daily_data['close'].iloc[-1])
                    print(f"     当前价格: {current_price:.2f}")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    # 3. 测试获取周线数据
    print("\n3️⃣ 测试周线数据...")
    for i, code in enumerate(test_codes[:3], 1):
        print(f"   {i}. {code}: ", end="")
        try:
            weekly_data = base_op.get_weekly_data(code, weeks=70)
            if weekly_data is None or weekly_data.empty:
                print("❌ 无数据")
            else:
                print(f"✅ {len(weekly_data)} 周数据")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    return True

def test_strategy_conditions():
    """测试策略条件"""
    print("\n🧪 测试策略条件")
    print("-" * 50)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    if len(all_codes) == 0:
        print("❌ 没有股票代码")
        return
    
    test_codes = all_codes[:20]  # 测试前20只
    
    print(f"测试 {len(test_codes)} 只股票的策略条件...")
    
    results = []
    
    for code in test_codes:
        try:
            # 检查ST
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            
            # 获取日线数据
            daily_data = base_op.get_daily_data(code, days=30)
            if daily_data is None or daily_data.empty or len(daily_data) < 6:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            
            # 检查cross_ma50策略
            from stock_operators.cross_ma_operator import CrossMAOperator
            cross_op = CrossMAOperator()
            cross_info = cross_op.calculate(code)
            cross_ma = cross_info.get('cross_ma_4w', False)
            
            # 检查weekly_mean_down策略
            weekly_data = base_op.get_weekly_data(code, weeks=70)
            weekly_mean_down = False
            
            if weekly_data is not None and not weekly_data.empty and len(weekly_data) >= 60:
                weekly_data = weekly_data.sort_values('date')
                weekly_data['close'] = pd.to_numeric(weekly_data['close'], errors='coerce')
                weekly_data = weekly_data.dropna(subset=['close'])
                
                if len(weekly_data) >= 60:
                    last60 = weekly_data['close'].tail(60)
                    prev30 = last60.iloc[:30]
                    recent30 = last60.iloc[30:]
                    
                    if not prev30.empty and not recent30.empty:
                        prev_mean = float(prev30.mean())
                        recent_mean = float(recent30.mean())
                        
                        if prev_mean > 0 and recent_mean > 0:
                            weekly_mean_down = recent_mean < prev_mean
            
            # 检查价格限制
            price_ok = current_price <= 150.0
            
            results.append({
                'code': code,
                'is_st': is_st,
                'has_daily': daily_data is not None and not daily_data.empty,
                'has_weekly': weekly_data is not None and not weekly_data.empty,
                'cross_ma': cross_ma,
                'weekly_mean_down': weekly_mean_down,
                'price_ok': price_ok,
                'current_price': current_price,
                'all_conditions': not is_st and cross_ma and weekly_mean_down and price_ok
            })
            
        except Exception as e:
            print(f"   {code}: ❌ 错误: {e}")
            continue
    
    # 分析结果
    if results:
        df = pd.DataFrame(results)
        
        print("\n📊 策略条件分析:")
        print(f"   总测试股票数: {len(df)}")
        print(f"   ST股票: {df['is_st'].sum()}")
        print(f"   有日线数据: {df['has_daily'].sum()}")
        print(f"   有周线数据: {df['has_weekly'].sum()}")
        print(f"   满足cross_ma50: {df['cross_ma'].sum()}")
        print(f"   满足weekly_mean_down: {df['weekly_mean_down'].sum()}")
        print(f"   价格≤150元: {df['price_ok'].sum()}")
        print(f"   满足所有条件: {df['all_conditions'].sum()}")
        
        # 显示满足条件的股票
        qualified = df[df['all_conditions']]
        if not qualified.empty:
            print("\n✅ 满足所有条件的股票:")
            for _, row in qualified.iterrows():
                print(f"   {row['code']}: {row['current_price']:.2f}元")
        else:
            print("\n❌ 没有股票满足所有条件")
            
            # 显示部分满足条件的股票
            print("\n📋 部分满足条件的股票:")
            for _, row in df.iterrows():
                conditions = []
                if not row['is_st']:
                    conditions.append("非ST")
                if row['cross_ma']:
                    conditions.append("cross_ma50")
                if row['weekly_mean_down']:
                    conditions.append("weekly_mean_down")
                if row['price_ok']:
                    conditions.append("价格≤150")
                
                if len(conditions) >= 2:  # 至少满足2个条件
                    print(f"   {row['code']}: {row['current_price']:.2f}元 - {', '.join(conditions)}")
    
    return results

def test_simplified_strategy():
    """测试简化版策略"""
    print("\n🧪 测试简化版策略")
    print("-" * 50)
    
    base_op = BaseOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    if len(all_codes) == 0:
        print("❌ 没有股票代码")
        return
    
    test_codes = all_codes[:30]
    
    print(f"测试简化版策略 (只要求有数据且价格≤150元)...")
    
    qualified = []
    
    for code in test_codes:
        try:
            # 获取日线数据
            daily_data = base_op.get_daily_data(code, days=10)
            if daily_data is None or daily_data.empty:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            
            # 简化条件：只要有数据且价格≤150元
            if current_price <= 150.0 and current_price > 0:
                qualified.append({
                    'code': code,
                    'price': current_price
                })
                
        except Exception as e:
            continue
    
    print(f"   找到 {len(qualified)} 只满足简化条件的股票")
    
    if qualified:
        print("\n✅ 简化版策略推荐:")
        for stock in qualified[:10]:  # 显示前10只
            print(f"   {stock['code']}: {stock['price']:.2f}元")
    
    return qualified

def main():
    """主函数"""
    print("🔍 GPU加速回测系统诊断工具")
    print("=" * 70)
    
    # 测试数据可用性
    data_ok = test_data_availability()
    
    if not data_ok:
        print("\n❌ 数据获取失败，无法继续诊断")
        return
    
    # 测试策略条件
    strategy_results = test_strategy_conditions()
    
    # 测试简化版策略
    simplified_results = test_simplified_strategy()
    
    print("\n" + "=" * 70)
    print("📋 诊断总结")
    print("=" * 70)
    
    if simplified_results:
        print("✅ 简化版策略可以找到符合条件的股票")
        print("💡 建议：放宽策略条件或使用简化版策略进行测试")
    else:
        print("❌ 即使简化版策略也找不到符合条件的股票")
        print("💡 建议：检查数据源和网络连接")
    
    print("\n🔧 可能的解决方案:")
    print("   1. 放宽策略条件（如降低数据要求）")
    print("   2. 使用简化版策略进行测试")
    print("   3. 检查数据源是否正常")
    print("   4. 增加测试股票数量")

if __name__ == "__main__":
    main()