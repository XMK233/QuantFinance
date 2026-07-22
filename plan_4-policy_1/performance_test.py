#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
性能测试脚本
比较原始回测系统和GPU加速回测系统的性能差异
"""

import argparse
import pandas as pd
import numpy as np
import time
import sys
from pathlib import Path
import subprocess
import json
from datetime import datetime
import matplotlib.pyplot as plt
import seaborn as sns
from tqdm import tqdm

# 设置中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

def run_backtest_system(use_gpu=False, num_workers=None, test_days=30):
    """运行回测系统并测量性能"""
    print(f"\n{'='*60}")
    print(f"🚀 运行{'GPU加速' if use_gpu else '原始'}回测系统")
    print(f"{'='*60}")
    
    # 构建命令
    cmd = [
        sys.executable, "accelerated_backtest.py",
        "--start-date", "2025-01-01",
        "--initial-capital", "50000",
        "--max-positions", "3",
        "--max-price", "150.0",
        "--output-dir", f"test_results_{'gpu' if use_gpu else 'cpu'}"
    ]
    
    if use_gpu:
        cmd.append("--no-gpu" if not use_gpu else "")
    if num_workers:
        cmd.extend(["--workers", str(num_workers)])
    
    # 移除空字符串
    cmd = [c for c in cmd if c]
    
    print(f"📋 执行命令: {' '.join(cmd)}")
    
    # 运行命令并计时
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 解析输出
        output = result.stdout
        
        # 提取关键信息
        total_days = None
        avg_time_per_day = None
        
        for line in output.split('\n'):
            if "加速回测完成" in line:
                # 查找耗时信息
                pass
            elif "总耗时:" in line:
                elapsed_time = float(line.split(":")[1].strip().replace("秒", ""))
            elif "平均每个交易日:" in line:
                avg_time_per_day = float(line.split(":")[1].strip().replace("秒", ""))
            elif "获取到" in line and "个交易日" in line:
                total_days = int(line.split("获取到")[1].split("个交易日")[0].strip())
        
        return {
            'success': True,
            'elapsed_time': elapsed_time,
            'avg_time_per_day': avg_time_per_day,
            'total_days': total_days,
            'output': output,
            'error': None
        }
        
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        return {
            'success': False,
            'elapsed_time': elapsed_time,
            'avg_time_per_day': None,
            'total_days': None,
            'output': e.stdout,
            'error': e.stderr
        }

def run_original_backtest():
    """运行原始回测系统"""
    print(f"\n{'='*60}")
    print("🚀 运行原始回测系统")
    print(f"{'='*60}")
    
    cmd = [
        sys.executable, "run_backtest.py", "full",
        "--start-date", "2025-01-01",
        "--initial-capital", "50000",
        "--max-positions", "3",
        "--max-price", "150.0",
        "--output-dir", "test_results_original"
    ]
    
    print(f"📋 执行命令: {' '.join(cmd)}")
    
    start_time = time.time()
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # 解析输出
        output = result.stdout
        
        # 提取关键信息
        total_days = None
        avg_time_per_day = None
        
        for line in output.split('\n'):
            if "回测完成" in line:
                # 查找耗时信息
                pass
            elif "总耗时" in line:
                elapsed_time = float(line.split(":")[1].strip().replace("秒", ""))
        
        return {
            'success': True,
            'elapsed_time': elapsed_time,
            'avg_time_per_day': avg_time_per_day,
            'total_days': total_days,
            'output': output,
            'error': None
        }
        
    except subprocess.CalledProcessError as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        return {
            'success': False,
            'elapsed_time': elapsed_time,
            'avg_time_per_day': None,
            'total_days': None,
            'output': e.stdout,
            'error': e.stderr
        }

def test_gpu_availability():
    """测试GPU可用性"""
    print("\n🔍 测试GPU可用性...")
    
    test_scripts = [
        """
import cupy as cp
print("✅ CuPy可用")
print(f"  CuPy版本: {cp.__version__}")
print(f"  GPU设备: {cp.cuda.runtime.getDeviceCount()}")
        """,
        """
import torch
print("✅ PyTorch可用")
print(f"  PyTorch版本: {torch.__version__}")
print(f"  CUDA可用: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"  GPU数量: {torch.cuda.device_count()}")
    print(f"  当前GPU: {torch.cuda.get_device_name(0)}")
        """
    ]
    
    results = []
    
    for i, script in enumerate(test_scripts):
        try:
            result = subprocess.run(
                [sys.executable, "-c", script],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                print(result.stdout.strip())
                results.append(True)
            else:
                print(f"❌ 测试脚本{i+1}失败: {result.stderr}")
                results.append(False)
                
        except subprocess.TimeoutExpired:
            print(f"❌ 测试脚本{i+1}超时")
            results.append(False)
        except Exception as e:
            print(f"❌ 测试脚本{i+1}异常: {e}")
            results.append(False)
    
    return any(results)

def run_performance_comparison(num_runs=3):
    """运行性能比较测试"""
    print("\n📊 开始性能比较测试")
    print(f"📈 每种配置运行 {num_runs} 次取平均值")
    
    results = []
    
    # 测试配置
    configs = [
        {'name': '原始系统', 'func': run_original_backtest, 'use_gpu': False},
        {'name': 'CPU并行', 'func': lambda: run_backtest_system(use_gpu=False, num_workers=4), 'use_gpu': False},
        {'name': 'GPU加速', 'func': lambda: run_backtest_system(use_gpu=True, num_workers=4), 'use_gpu': True},
    ]
    
    for config in configs:
        print(f"\n{'='*60}")
        print(f"🧪 测试配置: {config['name']}")
        print(f"{'='*60}")
        
        run_times = []
        successes = 0
        
        for i in range(num_runs):
            print(f"\n  第 {i+1}/{num_runs} 次运行...")
            
            result = config['func']()
            
            if result['success']:
                run_times.append(result['elapsed_time'])
                successes += 1
                print(f"  ✅ 成功 - 耗时: {result['elapsed_time']:.2f}秒")
            else:
                print(f"  ❌ 失败 - 错误: {result['error'][:100]}...")
        
        if successes > 0:
            avg_time = np.mean(run_times)
            std_time = np.std(run_times)
            
            results.append({
                'config': config['name'],
                'avg_time': avg_time,
                'std_time': std_time,
                'success_rate': successes / num_runs,
                'use_gpu': config['use_gpu']
            })
            
            print(f"\n  📊 统计结果:")
            print(f"    平均耗时: {avg_time:.2f}秒")
            print(f"    标准差: {std_time:.2f}秒")
            print(f"    成功率: {successes/num_runs:.1%}")
        else:
            print(f"\n  ⚠️  所有运行都失败")
    
    return results

def visualize_results(results, output_dir="performance_results"):
    """可视化性能测试结果"""
    if not results:
        print("⚠️  没有结果可可视化")
        return
    
    output_dir = Path(output_dir)
    output_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 转换为DataFrame
    df = pd.DataFrame(results)
    
    # 保存原始数据
    data_file = output_dir / f"performance_data_{timestamp}.csv"
    df.to_csv(data_file, index=False, encoding='utf-8-sig')
    print(f"💾 性能数据已保存: {data_file}")
    
    # 创建图表
    fig, axes = plt.subplots(2, 2, figsize=(15, 12))
    fig.suptitle('GPU加速回测系统性能比较', fontsize=16)
    
    # 1. 平均耗时柱状图
    ax1 = axes[0, 0]
    colors = ['skyblue' if not r['use_gpu'] else 'lightcoral' for r in results]
    bars = ax1.bar(range(len(results)), [r['avg_time'] for r in results], 
                   color=colors, alpha=0.8)
    
    # 添加误差条
    ax1.errorbar(range(len(results)), [r['avg_time'] for r in results],
                 yerr=[r['std_time'] for r in results], fmt='none', 
                 ecolor='black', capsize=5)
    
    ax1.set_xticks(range(len(results)))
    ax1.set_xticklabels([r['config'] for r in results], rotation=45, ha='right')
    ax1.set_ylabel('平均耗时 (秒)')
    ax1.set_title('不同配置的平均运行时间')
    ax1.grid(True, alpha=0.3)
    
    # 在柱子上添加数值
    for bar, avg_time in zip(bars, [r['avg_time'] for r in results]):
        height = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width()/2., height + 5,
                f'{avg_time:.1f}s', ha='center', va='bottom', fontsize=10)
    
    # 2. 成功率饼图
    ax2 = axes[0, 1]
    success_rates = [r['success_rate'] for r in results]
    labels = [r['config'] for r in results]
    
    wedges, texts, autotexts = ax2.pie(success_rates, labels=labels, autopct='%1.1f%%',
                                       startangle=90, colors=['lightgreen', 'lightblue', 'lightcoral'])
    ax2.set_title('不同配置的成功率')
    
    # 3. 加速比
    ax3 = axes[1, 0]
    if len(results) >= 2:
        baseline_time = results[0]['avg_time']
        speedup_ratios = [baseline_time / r['avg_time'] if r['avg_time'] > 0 else 0 
                         for r in results]
        
        ax3.bar(range(len(results)), speedup_ratios, color='lightseagreen', alpha=0.8)
        ax3.set_xticks(range(len(results)))
        ax3.set_xticklabels([r['config'] for r in results], rotation=45, ha='right')
        ax3.set_ylabel('加速比 (倍)')
        ax3.set_title(f'相对于"{results[0]["config"]}"的加速比')
        ax3.grid(True, alpha=0.3)
        
        # 添加数值
        for i, ratio in enumerate(speedup_ratios):
            ax3.text(i, ratio + 0.1, f'{ratio:.2f}x', ha='center', va='bottom', fontsize=10)
    
    # 4. 详细统计表
    ax4 = axes[1, 1]
    ax4.axis('tight')
    ax4.axis('off')
    
    # 创建表格数据
    table_data = []
    for r in results:
        table_data.append([
            r['config'],
            f"{r['avg_time']:.2f}s",
            f"{r['std_time']:.2f}s",
            f"{r['success_rate']:.1%}",
            "是" if r['use_gpu'] else "否"
        ])
    
    table = ax4.table(cellText=table_data,
                     colLabels=['配置', '平均耗时', '标准差', '成功率', '使用GPU'],
                     cellLoc='center',
                     loc='center')
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1.2, 1.5)
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图表
    chart_file = output_dir / f"performance_chart_{timestamp}.png"
    plt.savefig(chart_file, dpi=300, bbox_inches='tight')
    print(f"💾 性能图表已保存: {chart_file}")
    
    # 显示图表
    plt.show()
    
    # 生成报告
    report_file = output_dir / f"performance_report_{timestamp}.txt"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write("GPU加速回测系统性能测试报告\n")
        f.write("=" * 70 + "\n")
        f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"测试环境: Python {sys.version}\n")
        f.write(f"测试次数: 每种配置运行{len(results[0]) if results else 0}次\n")
        f.write("\n测试结果:\n")
        f.write("-" * 70 + "\n")
        
        for r in results:
            f.write(f"\n配置: {r['config']}\n")
            f.write(f"  平均耗时: {r['avg_time']:.2f}秒\n")
            f.write(f"  标准差: {r['std_time']:.2f}秒\n")
            f.write(f"  成功率: {r['success_rate']:.1%}\n")
            f.write(f"  使用GPU: {'是' if r['use_gpu'] else '否'}\n")
        
        # 计算加速效果
        if len(results) >= 2:
            baseline = results[0]
            for r in results[1:]:
                if r['avg_time'] > 0:
                    speedup = baseline['avg_time'] / r['avg_time']
                    improvement = (1 - r['avg_time'] / baseline['avg_time']) * 100
                    f.write(f"\n加速效果 ({r['config']} vs {baseline['config']}):\n")
                    f.write(f"  加速比: {speedup:.2f}倍\n")
                    f.write(f"  性能提升: {improvement:.1f}%\n")
    
    print(f"💾 性能报告已保存: {report_file}")
    
    return data_file, chart_file, report_file

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='GPU加速回测系统性能测试')
    parser.add_argument('--test-gpu', action='store_true',
                       help='测试GPU可用性')
    parser.add_argument('--runs', type=int, default=3,
                       help='每种配置的运行次数 (默认: 3)')
    parser.add_argument('--output-dir', type=str, default='performance_results',
                       help='输出目录 (默认: performance_results)')
    parser.add_argument('--skip-visualization', action='store_true',
                       help='跳过可视化图表')
    
    args = parser.parse_args()
    
    print("🎯 GPU加速回测系统性能测试")
    print("=" * 70)
    
    # 测试GPU可用性
    if args.test_gpu:
        gpu_available = test_gpu_availability()
        print(f"\n📊 GPU可用性: {'✅ 可用' if gpu_available else '❌ 不可用'}")
    
    # 运行性能比较测试
    print("\n" + "=" * 70)
    print("🚀 开始性能比较测试")
    print("=" * 70)
    
    results = run_performance_comparison(num_runs=args.runs)
    
    if not results:
        print("❌ 性能测试失败，没有有效结果")
        sys.exit(1)
    
    # 可视化结果
    if not args.skip_visualization:
        print("\n" + "=" * 70)
        print("📊 生成性能可视化图表")
        print("=" * 70)
        
        try:
            data_file, chart_file, report_file = visualize_results(
                results, 
                output_dir=args.output_dir
            )
            
            print(f"\n✅ 性能测试完成!")
            print(f"📊 结果已保存到目录: {args.output_dir}")
            print(f"📈 性能数据: {data_file}")
            print(f"📊 性能图表: {chart_file}")
            print(f"📋 性能报告: {report_file}")
            
        except Exception as e:
            print(f"⚠️  可视化失败: {e}")
            print("📋 原始结果:")
            for r in results:
                print(f"  {r['config']}: {r['avg_time']:.2f}秒 (成功率: {r['success_rate']:.1%})")
    else:
        print("\n📋 性能测试结果:")
        for r in results:
            print(f"  {r['config']}: {r['avg_time']:.2f}秒 (成功率: {r['success_rate']:.1%})")

if __name__ == "__main__":
    main()