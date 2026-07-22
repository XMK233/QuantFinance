#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
诊断GPU加速和交易问题
"""

import argparse
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import warnings
import time
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

def test_gpu_availability():
    """测试GPU可用性"""
    print("=" * 60)
    print("🧪 GPU可用性测试")
    print("=" * 60)
    
    # 测试CuPy
    try:
        import cupy as cp
        print("✅ CuPy 可用")
        print(f"   CuPy版本: {cp.__version__}")
        
        # 测试GPU计算
        print("  测试GPU计算...")
        start = time.time()
        x = cp.random.rand(10000, 10000)
        y = cp.random.rand(10000, 10000)
        z = cp.dot(x, y)
        gpu_time = time.time() - start
        print(f"  GPU矩阵乘法耗时: {gpu_time:.2f}秒")
        
        # 测试CPU计算对比
        print("  测试CPU计算对比...")
        start = time.time()
        x_cpu = np.random.rand(1000, 1000)
        y_cpu = np.random.rand(1000, 1000)
        z_cpu = np.dot(x_cpu, y_cpu)
        cpu_time = time.time() - start
        print(f"  CPU矩阵乘法耗时: {cpu_time:.2f}秒")
        
        print(f"  GPU加速比: {cpu_time/gpu_time:.1f}x")
        
        return True, "CuPy"
    except ImportError:
        print("❌ CuPy 不可用")
    
    # 测试PyTorch
    try:
        import torch
        print("✅ PyTorch 可用")
        print(f"   PyTorch版本: {torch.__version__}")
        
        # 检查CUDA
        if torch.cuda.is_available():
            print(f"  CUDA可用，设备: {torch.cuda.get_device_name(0)}")
            print(f"  GPU内存: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
            
            # 测试GPU计算
            print("  测试GPU计算...")
            start = time.time()
            x = torch.rand(10000, 10000, device='cuda')
            y = torch.rand(10000, 10000, device='cuda')
            z = torch.matmul(x, y)
            torch.cuda.synchronize()
            gpu_time = time.time() - start
            print(f"  GPU矩阵乘法耗时: {gpu_time:.2f}秒")
            
            # 测试CPU计算对比
            print("  测试CPU计算对比...")
            start = time.time()
            x_cpu = torch.rand(1000, 1000, device='cpu')
            y_cpu = torch.rand(1000, 1000, device='cpu')
            z_cpu = torch.matmul(x_cpu, y_cpu)
            cpu_time = time.time() - start
            print(f"  CPU矩阵乘法耗时: {cpu_time:.2f}秒")
            
            print(f"  GPU加速比: {cpu_time/gpu_time:.1f}x")
            
            return True, "PyTorch"
        else:
            print("❌ CUDA不可用")
            return False, "PyTorch (无CUDA)"
    except ImportError:
        print("❌ PyTorch 不可用")
    
    return False, "无GPU加速库"

def test_data_availability():
    """测试数据可用性"""
    print("\n" + "=" * 60)
    print("📊 数据可用性测试")
    print("=" * 60)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 1. 测试获取股票代码
    print("1️⃣ 获取沪深主板股票代码...")
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"   找到 {len(all_codes)} 只沪深主板股票")
    
    if len(all_codes) == 0:
        print("   ⚠️  没有找到股票代码，检查数据源")
        return False
    
    # 2. 测试获取股票信息
    print("2️⃣ 测试获取股票信息...")
    test_codes = all_codes[:5]
    for code in test_codes:
        try:
            info = base_op.get_stock_info(code)
            if info:
                name = info.get("name", "未知")
                print(f"   {code}: {name}")
            else:
                print(f"   {code}: 无信息")
        except Exception as e:
            print(f"   {code}: 错误 - {e}")
    
    # 3. 测试获取日线数据
    print("3️⃣ 测试获取日线数据...")
    for code in test_codes:
        try:
            daily_data = base_op.get_daily_data(code, days=10)
            if daily_data is not None and not daily_data.empty:
                current_price = float(daily_data['close'].iloc[-1])
                print(f"   {code}: 价格 {current_price:.2f}元, {len(daily_data)} 天数据")
            else:
                print(f"   {code}: 无日线数据")
        except Exception as e:
            print(f"   {code}: 错误 - {e}")
    
    # 4. 测试ST检测
    print("4️⃣ 测试ST检测...")
    for code in test_codes:
        try:
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            print(f"   {code}: {'是ST' if is_st else '非ST'}")
        except Exception as e:
            print(f"   {code}: ST检测错误 - {e}")
    
    return True

def test_strategy_conditions():
    """测试策略条件"""
    print("\n" + "=" * 60)
    print("🎯 策略条件测试")
    print("=" * 60)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    print(f"测试股票总数: {len(all_codes)}")
    
    # 测试不同策略条件
    max_price = 150.0
    test_codes = all_codes[:50]  # 测试前50只
    
    results = {
        'basic': 0,  # 基础条件：非ST，有数据，价格合适
        'cross_ma50': 0,  # cross_ma50策略
        'weekly_mean_down': 0,  # weekly_mean_down策略
        'both': 0  # 两个策略都满足
    }
    
    for code in test_codes:
        try:
            # 基础条件检查
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            if is_st:
                continue
            
            daily_data = base_op.get_daily_data(code, days=5)
            if daily_data is None or daily_data.empty or len(daily_data) < 3:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            if not (current_price > 0 and current_price <= max_price):
                continue
            
            results['basic'] += 1
            
            # cross_ma50策略检查
            try:
                from stock_operators.cross_ma_operator import CrossMAOperator
                cross_op = CrossMAOperator()
                cross_info = cross_op.calculate(code)
                cross_ma = cross_info.get('cross_ma_4w', False)
                if cross_ma:
                    results['cross_ma50'] += 1
            except Exception:
                pass
            
            # weekly_mean_down策略检查
            try:
                weekly_data = base_op.get_weekly_data(code, weeks=70)
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
                            
                            if prev_mean > 0 and recent_mean > 0 and recent_mean < prev_mean:
                                results['weekly_mean_down'] += 1
            except Exception:
                pass
            
            # 两个策略都满足
            if results['cross_ma50'] > 0 and results['weekly_mean_down'] > 0:
                results['both'] += 1
                
        except Exception as e:
            continue
    
    print("策略条件测试结果:")
    print(f"  基础条件满足: {results['basic']} 只")
    print(f"  cross_ma50策略满足: {results['cross_ma50']} 只")
    print(f"  weekly_mean_down策略满足: {results['weekly_mean_down']} 只")
    print(f"  两个策略都满足: {results['both']} 只")
    
    # 分析问题
    print("\n🔍 问题分析:")
    if results['basic'] == 0:
        print("  ❌ 基础条件都无法满足 - 检查数据源和价格限制")
    elif results['both'] == 0:
        print("  ⚠️  两个策略同时满足的股票为0 - 策略条件太严格")
        print("  💡 建议: 放宽策略条件或使用单一策略")
    else:
        print("  ✅ 策略条件正常，有符合条件的股票")
    
    return results

def test_simple_trading():
    """测试简单交易逻辑"""
    print("\n" + "=" * 60)
    print("💰 简单交易逻辑测试")
    print("=" * 60)
    
    base_op = BaseOperator()
    st_op = STStockOperator()
    
    # 获取股票代码
    all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
    max_price = 150.0
    
    # 使用终极简化策略
    recommendations = []
    
    for code in all_codes[:30]:  # 测试前30只
        try:
            # 检查ST
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            if is_st:
                continue
            
            # 获取日线数据
            daily_data = base_op.get_daily_data(code, days=5)
            if daily_data is None or daily_data.empty or len(daily_data) < 3:
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            if not (current_price > 0 and current_price <= max_price):
                continue
            
            # 获取股票名称
            info = base_op.get_stock_info(code)
            stock_name = info.get("name", "") if info else ""
            
            recommendations.append({
                'stock_code': code,
                'stock_name': stock_name,
                'signal': 'BUY',
                'confidence': 0.6,
                'current_price': current_price,
                'reasons': 'ultimate_simplified'
            })
            
            if len(recommendations) >= 5:  # 找到5只就停止
                break
                
        except Exception as e:
            continue
    
    print(f"找到 {len(recommendations)} 只符合条件的股票:")
    for rec in recommendations:
        print(f"  {rec['stock_code']} ({rec['stock_name']}): {rec['current_price']:.2f}元")
    
    if len(recommendations) > 0:
        print("✅ 交易逻辑正常，可以产生交易")
        return True
    else:
        print("❌ 交易逻辑有问题，无法找到符合条件的股票")
        return False

def main():
    parser = argparse.ArgumentParser(description='诊断GPU加速和交易问题')
    parser.add_argument('--test-all', action='store_true', help='运行所有测试')
    parser.add_argument('--test-gpu', action='store_true', help='只测试GPU')
    parser.add_argument('--test-data', action='store_true', help='只测试数据')
    parser.add_argument('--test-strategy', action='store_true', help='只测试策略')
    parser.add_argument('--test-trading', action='store_true', help='只测试交易')
    
    args = parser.parse_args()
    
    if args.test_all or not any([args.test_gpu, args.test_data, args.test_strategy, args.test_trading]):
        print("🚀 运行所有诊断测试...")
        test_gpu_availability()
        test_data_availability()
        test_strategy_conditions()
        test_simple_trading()
    else:
        if args.test_gpu:
            test_gpu_availability()
        if args.test_data:
            test_data_availability()
        if args.test_strategy:
            test_strategy_conditions()
        if args.test_trading:
            test_simple_trading()
    
    print("\n" + "=" * 60)
    print("📋 诊断总结")
    print("=" * 60)
    print("1. GPU加速问题: 需要确保计算真正在GPU上执行")
    print("2. 交易问题: 策略条件可能太严格，需要放宽条件")
    print("3. 建议: 使用终极简化策略确保有交易，然后优化GPU加速")

if __name__ == "__main__":
    main()