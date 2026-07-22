#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修复版简单测试 - 修复get_stock_name问题
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

def test_data_basic():
    """测试基础数据获取"""
    print("🧪 测试基础数据获取")
    print("-" * 50)
    
    base_op = BaseOperator()
    
    # 1. 测试获取股票代码
    print("1️⃣ 获取沪深主板股票代码...")
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"   找到 {len(all_codes)} 只沪深主板股票")
    
    if len(all_codes) == 0:
        print("   ❌ 没有找到任何股票代码")
        return False
    
    # 2. 测试获取股票信息
    print("\n2️⃣ 测试获取股票信息...")
    test_codes = all_codes[:5]
    
    for i, code in enumerate(test_codes, 1):
        print(f"   {i}. {code}: ", end="")
        try:
            info = base_op.get_stock_info(code)
            if isinstance(info, dict):
                name = info.get("name", "")
                print(f"✅ {name}")
            else:
                print("❌ 无法获取信息")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    # 3. 测试获取日线数据
    print("\n3️⃣ 测试获取日线数据...")
    for i, code in enumerate(test_codes, 1):
        print(f"   {i}. {code}: ", end="")
        try:
            daily_data = base_op.get_daily_data(code, days=10)
            if daily_data is None or daily_data.empty:
                print("❌ 无数据")
            else:
                print(f"✅ {len(daily_data)} 天数据")
                if not daily_data.empty:
                    current_price = float(daily_data['close'].iloc[-1])
                    print(f"     当前价格: {current_price:.2f}")
        except Exception as e:
            print(f"❌ 错误: {e}")
    
    return True

def test_simplest_strategy():
    """测试最简单策略"""
    print("\n🧪 测试最简单策略")
    print("-" * 50)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"找到 {len(all_codes)} 只沪深主板股票")
    
    if len(all_codes) == 0:
        print("❌ 没有股票代码")
        return []
    
    # 只测试前20只股票
    test_codes = all_codes[:20]
    
    print(f"\n测试 {len(test_codes)} 只股票的最简单策略条件:")
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
            daily_data = base_op.get_daily_data(code, days=5)
            if daily_data is None or daily_data.empty:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            
            # 检查价格限制
            if not (current_price > 0 and current_price <= 150.0):
                continue
            
            # 获取股票名称
            info = base_op.get_stock_info(code)
            stock_name = ""
            if isinstance(info, dict):
                stock_name = info.get("name", "")
            
            qualified.append({
                'code': code,
                'name': stock_name,
                'price': current_price
            })
            
            print(f"  ✅ {code} ({stock_name}): {current_price:.2f}元")
            
        except Exception as e:
            print(f"  {code}: ❌ 错误: {e}")
            continue
    
    print(f"\n✅ 找到 {len(qualified)} 只满足最简单条件的股票")
    
    return qualified

def test_gpu_acceleration():
    """测试GPU加速"""
    print("\n🧪 测试GPU加速")
    print("-" * 50)
    
    # 测试CuPy
    try:
        import cupy as cp
        print("✅ CuPy 可用")
        
        # 创建一个简单的GPU计算测试
        print("  测试GPU计算...")
        x = cp.arange(1000000, dtype=cp.float32)
        y = cp.arange(1000000, dtype=cp.float32)
        
        start = time.time()
        z = x + y
        cp.cuda.Stream.null.synchronize()
        gpu_time = time.time() - start
        
        print(f"  GPU计算时间: {gpu_time:.4f}秒")
        
    except ImportError:
        print("❌ CuPy 不可用")
    
    # 测试PyTorch
    try:
        import torch
        print("✅ PyTorch 可用")
        
        # 检查是否有GPU
        if torch.cuda.is_available():
            print(f"  GPU设备: {torch.cuda.get_device_name(0)}")
            print(f"  GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
            
            # 测试GPU计算
            print("  测试PyTorch GPU计算...")
            x = torch.randn(1000000, device='cuda')
            y = torch.randn(1000000, device='cuda')
            
            start = time.time()
            z = x + y
            torch.cuda.synchronize()
            gpu_time = time.time() - start
            
            print(f"  PyTorch GPU计算时间: {gpu_time:.4f}秒")
        else:
            print("  ⚠️  PyTorch GPU不可用")
            
    except ImportError:
        print("❌ PyTorch 不可用")

def main():
    """主函数"""
    print("🔍 修复版简单测试")
    print("=" * 70)
    
    import time
    
    # 测试基础数据
    data_ok = test_data_basic()
    
    if not data_ok:
        print("\n❌ 基础数据测试失败")
        return
    
    # 测试最简单策略
    qualified_stocks = test_simplest_strategy()
    
    if not qualified_stocks:
        print("\n❌ 没有找到任何符合条件的股票")
        print("\n💡 可能的原因:")
        print("   1. 数据源问题 - 无法获取股票数据")
        print("   2. 网络连接问题 - 无法访问数据API")
        print("   3. 所有股票都是ST股")
        print("   4. 所有股票价格都超过150元")
        return
    
    # 测试GPU加速
    test_gpu_acceleration()
    
    print("\n" + "=" * 70)
    print("📋 测试总结")
    print("=" * 70)
    
    print(f"✅ 基础数据测试通过")
    print(f"✅ 最简单策略测试通过")
    print(f"📊 找到 {len(qualified_stocks)} 只符合条件的股票")
    
    print("\n🔧 建议:")
    print("   1. 使用修复版本的回测系统")
    print("   2. 确保数据源正常工作")
    print("   3. 检查网络连接")
    print("   4. 增加测试股票数量")

if __name__ == "__main__":
    main()