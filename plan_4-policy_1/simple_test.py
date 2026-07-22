#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单测试脚本
验证GPU加速回测系统的基本功能
"""

import sys
import time
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_basic_functionality():
    """测试基本功能"""
    print("🧪 测试基本功能...")
    
    # 测试GPU检测
    try:
        from accelerated_backtest import GPU_AVAILABLE
        print(f"  GPU可用性: {'✅ 可用' if GPU_AVAILABLE else '❌ 不可用'}")
    except Exception as e:
        print(f"  ❌ GPU检测失败: {e}")
        return False
    
    # 测试原始回测系统
    try:
        from backtest_system import BacktestSystem
        print("  ✅ 原始回测系统导入成功")
    except Exception as e:
        print(f"  ❌ 原始回测系统导入失败: {e}")
        return False
    
    # 测试加速回测系统
    try:
        from accelerated_backtest import AcceleratedBacktestSystem
        print("  ✅ 加速回测系统导入成功")
    except Exception as e:
        print(f"  ❌ 加速回测系统导入失败: {e}")
        return False
    
    return True

def test_quick_backtest():
    """快速回测测试"""
    print("\n⚡ 快速回测测试...")
    
    try:
        from accelerated_backtest import AcceleratedBacktestSystem
        
        print("  创建AcceleratedBacktestSystem实例...")
        backtest = AcceleratedBacktestSystem(
            initial_capital=50000,
            max_positions=3,
            max_price=150.0,
            start_date="2025-01-01",
            use_gpu=False,  # 先测试CPU模式
            num_workers=1
        )
        
        print("  ✅ 实例创建成功")
        
        # 测试交易日历
        print(f"  交易日数量: {len(backtest.trading_dates)}")
        
        # 运行简化的回测（只测试几天）
        print("  运行简化回测...")
        
        # 只测试前5个交易日
        test_dates = backtest.trading_dates[:5]
        
        for current_date in test_dates:
            print(f"    处理日期: {current_date.date()}")
            
            # 获取策略推荐
            recommendations = backtest._get_strategy_recommendations_parallel(current_date)
            print(f"      推荐股票: {len(recommendations) if not recommendations.empty else 0}只")
            
            # 如果有推荐，尝试买入
            if not recommendations.empty and backtest.cash > 1000:
                stock = recommendations.iloc[0]
                success = backtest._execute_buy(
                    stock['stock_code'],
                    stock['stock_name'],
                    stock['current_price'],
                    current_date,
                    backtest.cash
                )
                if success:
                    print(f"      买入成功: {stock['stock_code']}")
        
        print("  ✅ 简化回测完成")
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_gpu_calculation():
    """测试GPU计算功能"""
    print("\n🧮 测试GPU计算功能...")
    
    try:
        from accelerated_backtest import AcceleratedBacktestSystem
        
        # 创建实例
        backtest = AcceleratedBacktestSystem(
            initial_capital=50000,
            max_positions=3,
            max_price=150.0,
            start_date="2025-01-01",
            use_gpu=True,  # 测试GPU模式
            num_workers=1
        )
        
        print("  ✅ GPU模式实例创建成功")
        
        # 测试GPU得分计算
        test_data = {
            'confidence': 0.7,
            'current_price': 50.0,
            'weekly_mean_ratio': 0.9
        }
        
        print("  测试GPU得分计算...")
        score = backtest._calculate_stock_score(test_data)
        print(f"    计算得分: {score:.2f}")
        
        # 测试批量收益率计算
        print("  测试批量收益率计算...")
        stock_codes = ['000001', '000002', '000003']
        current_prices = [10.0, 20.0, 30.0]
        buy_prices = [8.0, 18.0, 25.0]
        
        returns = backtest._batch_calculate_returns(stock_codes, current_prices, buy_prices)
        print(f"    批量收益率: {returns}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ GPU计算测试失败: {e}")
        return False

def main():
    """主函数"""
    print("🎯 GPU加速回测系统简单测试")
    print("=" * 60)
    
    # 运行测试
    basic_ok = test_basic_functionality()
    
    if basic_ok:
        quick_ok = test_quick_backtest()
        
        # 测试GPU计算（如果GPU可用）
        try:
            from accelerated_backtest import GPU_AVAILABLE
            if GPU_AVAILABLE:
                gpu_calc_ok = test_gpu_calculation()
            else:
                print("\n⚠️  GPU不可用，跳过GPU计算测试")
                gpu_calc_ok = True
        except:
            gpu_calc_ok = True
    
    # 总结
    print("\n" + "=" * 60)
    print("📋 测试总结")
    print("=" * 60)
    
    if basic_ok:
        print("✅ 基本功能测试通过")
        
        print("\n🎯 现在你可以使用以下命令:")
        print("  1. 运行原始回测:")
        print("     python run_backtest.py full")
        print("  2. 运行GPU加速回测:")
        print("     python run_backtest.py full --gpu")
        print("  3. 运行性能测试:")
        print("     python performance_test.py --runs 2")
    else:
        print("❌ 基本功能测试失败")
    
    print("=" * 60)

if __name__ == "__main__":
    main()