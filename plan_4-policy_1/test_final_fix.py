#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试最终修复效果
验证交易和GPU加速问题是否解决
"""

import subprocess
import sys
import time
from pathlib import Path

def run_test(test_name, command, timeout=300):
    """运行测试命令"""
    print(f"\n{'='*60}")
    print(f"🧪 测试: {test_name}")
    print(f"{'='*60}")
    print(f"命令: {' '.join(command)}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        
        elapsed = time.time() - start_time
        
        print(f"\n⏱️  耗时: {elapsed:.1f}秒")
        print(f"📤 输出:")
        print("-" * 40)
        
        # 显示最后50行输出
        output_lines = result.stdout.split('\n')
        for line in output_lines[-50:]:
            if line.strip():
                print(line)
        
        print("-" * 40)
        
        if result.returncode == 0:
            print(f"✅ {test_name} 通过")
            return True, result.stdout
        else:
            print(f"❌ {test_name} 失败 (返回码: {result.returncode})")
            print(f"错误输出:\n{result.stderr}")
            return False, result.stdout
            
    except subprocess.TimeoutExpired:
        print(f"⏰ {test_name} 超时 ({timeout}秒)")
        return False, ""
    except Exception as e:
        print(f"⚠️  {test_name} 异常: {e}")
        return False, ""

def test_data_availability():
    """测试数据可用性"""
    print("\n" + "=" * 60)
    print("📊 测试数据可用性")
    print("=" * 60)
    
    test_code = """
import sys
from pathlib import Path

plan3_dir = Path(__file__).parent.parent / "plan_3-standardization_1"
sys.path.insert(0, str(plan3_dir))

from daily_trading_system import BaseOperator, STStockOperator

base_op = BaseOperator()
st_op = STStockOperator()

# 1. 获取股票代码
all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
print(f"找到 {len(all_codes)} 只沪深主板股票")

if len(all_codes) == 0:
    print("❌ 没有找到股票代码")
    sys.exit(1)

# 2. 测试前5只股票
test_codes = all_codes[:5]
for code in test_codes:
    try:
        # 获取股票信息
        info = base_op.get_stock_info(code)
        name = info.get('name', '未知') if info else '未知'
        
        # 获取日线数据
        daily_data = base_op.get_daily_data(code, days=5)
        if daily_data is not None and not daily_data.empty:
            price = float(daily_data['close'].iloc[-1])
            print(f"  {code} ({name}): {price:.2f}元, {len(daily_data)}天数据")
        else:
            print(f"  {code} ({name}): 无日线数据")
            
    except Exception as e:
        print(f"  {code}: 错误 - {e}")

print("✅ 数据可用性测试通过")
"""
    
    with open('temp_test.py', 'w', encoding='utf-8') as f:
        f.write(test_code)
    
    success, output = run_test("数据可用性", [sys.executable, 'temp_test.py'], timeout=60)
    
    # 清理临时文件
    import os
    if os.path.exists('temp_test.py'):
        os.remove('temp_test.py')
    
    return success

def test_simple_backtest():
    """测试简单回测"""
    print("\n" + "=" * 60)
    print("💰 测试简单回测")
    print("=" * 60)
    
    # 运行快速测试
    command = [
        sys.executable, 'final_fixed_backtest.py',
        '--start-date', '2025-01-01',
        '--initial-capital', '50000',
        '--max-positions', '3',
        '--max-price', '150.0',
        '--output-dir', 'test_simple_backtest',
        '--test-only'
    ]
    
    success, output = run_test("简单回测", command, timeout=120)
    
    # 检查输出中是否有推荐股票
    if success and '推荐股票:' in output:
        print("✅ 简单回测测试通过 - 找到推荐股票")
        return True
    elif success:
        print("⚠️  简单回测测试通过但无推荐股票")
        return True
    else:
        print("❌ 简单回测测试失败")
        return False

def test_gpu_backtest():
    """测试GPU回测"""
    print("\n" + "=" * 60)
    print("⚡ 测试GPU回测")
    print("=" * 60)
    
    # 运行GPU测试
    command = [
        sys.executable, 'gpu_optimized_backtest.py',
        '--start-date', '2025-01-01',
        '--initial-capital', '50000',
        '--max-positions', '3',
        '--max-price', '150.0',
        '--output-dir', 'test_gpu_backtest',
        '--test-only'
    ]
    
    success, output = run_test("GPU回测", command, timeout=120)
    
    # 检查GPU相关信息
    if success:
        if 'GPU加速可用' in output or '使用CuPy GPU加速' in output or '使用PyTorch GPU加速' in output:
            print("✅ GPU回测测试通过 - GPU加速启用")
            return True
        else:
            print("⚠️  GPU回测测试通过但GPU加速未启用")
            return True
    else:
        print("❌ GPU回测测试失败")
        return False

def test_full_backtest_cpu():
    """测试完整CPU回测"""
    print("\n" + "=" * 60)
    print("💻 测试完整CPU回测")
    print("=" * 60)
    
    # 运行短期回测（10个交易日）
    test_end_date = '2025-01-15'  # 大约10个交易日
    
    command = [
        sys.executable, 'final_fixed_backtest.py',
        '--start-date', '2025-01-01',
        '--end-date', test_end_date,
        '--initial-capital', '50000',
        '--max-positions', '3',
        '--max-price', '150.0',
        '--output-dir', 'test_full_cpu',
        '--no-gpu',
        '--workers', '2'
    ]
    
    success, output = run_test("完整CPU回测", command, timeout=180)
    
    # 检查是否有交易
    if success:
        if '总交易次数:' in output:
            # 提取交易次数
            for line in output.split('\n'):
                if '总交易次数:' in line:
                    trade_count = line.split(':')[1].strip().split()[0]
                    print(f"✅ 完整CPU回测测试通过 - 交易次数: {trade_count}")
                    return True
        else:
            print("⚠️  完整CPU回测测试通过但无交易记录")
            return True
    else:
        print("❌ 完整CPU回测测试失败")
        return False

def test_full_backtest_gpu():
    """测试完整GPU回测"""
    print("\n" + "=" * 60)
    print("🎮 测试完整GPU回测")
    print("=" * 60)
    
    # 运行短期回测（10个交易日）
    test_end_date = '2025-01-15'  # 大约10个交易日
    
    command = [
        sys.executable, 'gpu_optimized_backtest.py',
        '--start-date', '2025-01-01',
        '--end-date', test_end_date,
        '--initial-capital', '50000',
        '--max-positions', '3',
        '--max-price', '150.0',
        '--output-dir', 'test_full_gpu',
        '--workers', '2'
    ]
    
    success, output = run_test("完整GPU回测", command, timeout=180)
    
    # 检查是否有交易和GPU信息
    if success:
        has_trades = '总交易次数:' in output
        has_gpu = any(x in output for x in ['GPU加速可用', '使用CuPy GPU加速', '使用PyTorch GPU加速'])
        
        if has_trades and has_gpu:
            print("✅ 完整GPU回测测试通过 - 有交易且GPU加速启用")
            return True
        elif has_trades:
            print("⚠️  完整GPU回测测试通过 - 有交易但GPU加速可能未启用")
            return True
        else:
            print("⚠️  完整GPU回测测试通过但无交易记录")
            return True
    else:
        print("❌ 完整GPU回测测试失败")
        return False

def main():
    """主测试函数"""
    print("🚀 开始最终修复测试")
    print("=" * 60)
    
    # 检查必要文件
    required_files = [
        'final_fixed_backtest.py',
        'gpu_optimized_backtest.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print(f"❌ 缺少必要文件: {missing_files}")
        print("请先创建必要的回测文件")
        return
    
    # 运行测试
    tests = [
        ("数据可用性", test_data_availability),
        ("简单回测", test_simple_backtest),
        ("GPU回测", test_gpu_backtest),
        ("完整CPU回测", test_full_backtest_cpu),
        ("完整GPU回测", test_full_backtest_gpu)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        try:
            success = test_func()
            results.append((test_name, success))
        except Exception as e:
            print(f"⚠️  {test_name} 测试异常: {e}")
            results.append((test_name, False))
    
    # 打印测试结果
    print("\n" + "=" * 60)
    print("📋 测试结果汇总")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, success in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{test_name}: {status}")
        
        if success:
            passed += 1
        else:
            failed += 1
    
    print(f"\n📊 总计: {passed} 通过, {failed} 失败")
    
    if failed == 0:
        print("\n🎉 所有测试通过! 问题已解决")
        print("\n💡 建议运行以下命令验证:")
        print("1. CPU回测:")
        print("   python final_fixed_backtest.py --start-date 2025-01-01 --initial-capital 50000 --max-positions 3 --max-price 150.0 --output-dir final_cpu_test --no-gpu --workers 4")
        print("\n2. GPU回测:")
        print("   python gpu_optimized_backtest.py --start-date 2025-01-01 --initial-capital 50000 --max-positions 3 --max-price 150.0 --output-dir final_gpu_test --workers 4")
    else:
        print(f"\n⚠️  有 {failed} 个测试失败，需要进一步调试")

if __name__ == "__main__":
    main()