#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试GPU加速回测系统
验证基本功能和性能
"""

import sys
import time
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_gpu_detection():
    """测试GPU检测功能"""
    print("🔍 测试GPU检测功能...")
    
    try:
        from accelerated_backtest import GPU_AVAILABLE
        print(f"  GPU可用性: {'✅ 可用' if GPU_AVAILABLE else '❌ 不可用'}")
        return GPU_AVAILABLE
    except Exception as e:
        print(f"  ❌ GPU检测失败: {e}")
        return False

def test_accelerated_backtest_class():
    """测试AcceleratedBacktestSystem类"""
    print("\n🧪 测试AcceleratedBacktestSystem类...")
    
    try:
        from accelerated_backtest import AcceleratedBacktestSystem
        
        # 创建实例
        print("  创建AcceleratedBacktestSystem实例...")
        backtest = AcceleratedBacktestSystem(
            initial_capital=50000,
            max_positions=3,
            max_price=150.0,
            start_date="2025-01-01",
            use_gpu=False,  # 先测试CPU模式
            num_workers=2
        )
        
        print("  ✅ 实例创建成功")
        
        # 测试交易日历获取
        print("  测试交易日历获取...")
        trading_dates = backtest.trading_dates
        print(f"    交易日数量: {len(trading_dates)}")
        
        if len(trading_dates) > 0:
            print(f"    第一个交易日: {trading_dates[0]}")
            print(f"    最后一个交易日: {trading_dates[-1]}")
        
        # 测试策略推荐
        print("  测试策略推荐...")
        if len(trading_dates) > 0:
            test_date = trading_dates[0]
            recommendations = backtest._get_strategy_recommendations_parallel(test_date)
            print(f"    推荐股票数量: {len(recommendations) if not recommendations.empty else 0}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_original_backtest():
    """测试原始回测系统"""
    print("\n🧪 测试原始回测系统...")
    
    try:
        from backtest_system import BacktestSystem
        
        # 创建实例
        print("  创建BacktestSystem实例...")
        backtest = BacktestSystem(
            initial_capital=50000,
            max_positions=3,
            max_price=150.0,
            start_date="2025-01-01"
        )
        
        print("  ✅ 实例创建成功")
        
        # 测试交易日历获取
        print("  测试交易日历获取...")
        trading_dates = backtest.trading_dates
        print(f"    交易日数量: {len(trading_dates)}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False

def test_command_line_interface():
    """测试命令行接口"""
    print("\n🧪 测试命令行接口...")
    
    import subprocess
    
    # 测试原始版本
    print("  测试原始版本命令...")
    cmd = [
        sys.executable, "run_backtest.py", "full",
        "--start-date", "2025-01-01",
        "--initial-capital", "50000",
        "--max-positions", "3",
        "--max-price", "150.0",
        "--output-dir", "test_cli_original"
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("  ✅ 原始版本命令执行成功")
        else:
            print(f"  ❌ 原始版本命令执行失败: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("  ⚠️  原始版本命令超时")
    except Exception as e:
        print(f"  ❌ 原始版本命令异常: {e}")
    
    # 测试GPU加速版本
    print("  测试GPU加速版本命令...")
    cmd_gpu = [
        sys.executable, "run_backtest.py", "full",
        "--start-date", "2025-01-01",
        "--initial-capital", "50000",
        "--max-positions", "3",
        "--max-price", "150.0",
        "--output-dir", "test_cli_gpu",
        "--gpu"
    ]
    
    try:
        result = subprocess.run(cmd_gpu, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            print("  ✅ GPU加速版本命令执行成功")
        else:
            print(f"  ❌ GPU加速版本命令执行失败: {result.stderr[:200]}")
    except subprocess.TimeoutExpired:
        print("  ⚠️  GPU加速版本命令超时")
    except Exception as e:
        print(f"  ❌ GPU加速版本命令异常: {e}")

def quick_performance_test():
    """快速性能测试"""
    print("\n⚡ 快速性能测试...")
    
    import subprocess
    import time
    
    test_configs = [
        {"name": "原始系统", "gpu": False, "workers": None},
        {"name": "CPU并行", "gpu": False, "workers": 4},
        {"name": "GPU加速", "gpu": True, "workers": 4},
    ]
    
    results = []
    
    for config in test_configs:
        print(f"\n  测试配置: {config['name']}")
        
        # 构建命令
        cmd = [
            sys.executable, "run_backtest.py", "full",
            "--start-date", "2025-01-01",
            "--initial-capital", "50000",
            "--max-positions", "3",
            "--max-price", "150.0",
            "--output-dir", f"quick_test_{config['name']}",
        ]
        
        if config['gpu']:
            cmd.append("--gpu")
        
        if config['workers']:
            cmd.extend(["--workers", str(config['workers'])])
        
        # 运行测试
        start_time = time.time()
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120  # 2分钟超时
            )
            
            end_time = time.time()
            elapsed_time = end_time - start_time
            
            if result.returncode == 0:
                print(f"    ✅ 成功 - 耗时: {elapsed_time:.2f}秒")
                results.append({
                    'config': config['name'],
                    'time': elapsed_time,
                    'success': True
                })
            else:
                print(f"    ❌ 失败 - 错误: {result.stderr[:100]}...")
                results.append({
                    'config': config['name'],
                    'time': elapsed_time,
                    'success': False
                })
                
        except subprocess.TimeoutExpired:
            print(f"    ⚠️  超时 - 超过120秒")
            results.append({
                'config': config['name'],
                'time': 120,
                'success': False
            })
        except Exception as e:
            print(f"    ❌ 异常: {e}")
            results.append({
                'config': config['name'],
                'time': None,
                'success': False
            })
    
    # 打印结果
    print("\n📊 快速性能测试结果:")
    print("-" * 40)
    
    for result in results:
        if result['success']:
            print(f"  {result['config']}: {result['time']:.2f}秒")
        else:
            print(f"  {result['config']}: 失败")

def main():
    """主函数"""
    print("🎯 GPU加速回测系统测试")
    print("=" * 70)
    
    # 运行测试
    gpu_available = test_gpu_detection()
    
    accelerated_ok = test_accelerated_backtest_class()
    
    original_ok = test_original_backtest()
    
    test_command_line_interface()
    
    # 询问是否运行快速性能测试
    print("\n" + "=" * 70)
    response = input("是否运行快速性能测试? (y/n): ").strip().lower()
    
    if response == 'y':
        quick_performance_test()
    
    # 总结
    print("\n" + "=" * 70)
    print("📋 测试总结")
    print("=" * 70)
    
    print(f"GPU可用性: {'✅ 可用' if gpu_available else '❌ 不可用'}")
    print(f"加速回测系统: {'✅ 正常' if accelerated_ok else '❌ 异常'}")
    print(f"原始回测系统: {'✅ 正常' if original_ok else '❌ 异常'}")
    
    if gpu_available and accelerated_ok and original_ok:
        print("\n✅ 所有测试通过!")
        print("\n🎯 现在你可以使用以下命令运行GPU加速回测:")
        print("  python run_backtest.py full --gpu --workers 4")
        print("\n📊 或者运行性能比较测试:")
        print("  python performance_test.py --runs 3")
    else:
        print("\n⚠️  部分测试失败，请检查错误信息")
    
    print("=" * 70)

if __name__ == "__main__":
    main()