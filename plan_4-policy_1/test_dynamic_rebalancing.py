#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试动态换仓逻辑
"""

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

from backtest_system import BacktestSystem

def test_position_evaluation():
    """测试持仓评估"""
    print("🧪 测试持仓评估逻辑...")
    
    # 创建回测系统
    backtest = BacktestSystem(
        initial_capital=50000,
        max_positions=3,
        max_price=150.0,
        start_date='2025-01-01'
    )
    
    # 模拟一些持仓
    from datetime import datetime, timedelta
    
    # 添加测试持仓
    backtest.positions = {
        '000001': {
            'shares': 1000,
            'buy_price': 10.0,
            'buy_date': datetime(2025, 1, 1),
            'stock_name': '平安银行'
        },
        '000002': {
            'shares': 500,
            'buy_price': 20.0,
            'buy_date': datetime(2025, 2, 1),
            'stock_name': '万科A'
        },
        '000003': {
            'shares': 300,
            'buy_price': 30.0,
            'buy_date': datetime(2025, 3, 1),
            'stock_name': '中国平安'
        }
    }
    
    # 设置现金
    backtest.cash = 10000
    
    # 测试评估函数
    test_date = datetime(2025, 6, 1)
    
    # 由于我们无法获取真实价格数据，这里测试函数结构
    print("  测试 _evaluate_position_performance 函数结构...")
    
    # 检查函数是否存在
    if hasattr(backtest, '_evaluate_position_performance'):
        print("  ✅ 函数存在")
        
        # 尝试调用（可能会因为缺少数据而返回空列表）
        try:
            performance = backtest._evaluate_position_performance(test_date)
            print(f"  ✅ 函数调用成功，返回 {len(performance)} 个持仓评估")
            
            if performance:
                for perf in performance:
                    print(f"    股票: {perf['stock_code']}, 得分: {perf['score']:.2f}")
        except Exception as e:
            print(f"  ⚠️  函数调用失败: {e}")
    else:
        print("  ❌ 函数不存在")
    
    print("\n🧪 测试股票得分计算...")
    
    # 测试股票得分计算
    if hasattr(backtest, '_calculate_stock_score'):
        print("  ✅ _calculate_stock_score 函数存在")
        
        # 创建测试数据
        test_stock = {
            'stock_code': '000004',
            'stock_name': '测试股票',
            'current_price': 25.0,
            'confidence': 0.7,
            'weekly_mean_ratio': 0.9
        }
        
        try:
            score = backtest._calculate_stock_score(test_stock)
            print(f"  ✅ 得分计算成功: {score:.2f}")
            print(f"    价格: {test_stock['current_price']}元")
            print(f"    置信度: {test_stock['confidence']}")
            print(f"    周均价比率: {test_stock['weekly_mean_ratio']}")
        except Exception as e:
            print(f"  ⚠️  得分计算失败: {e}")
    else:
        print("  ❌ _calculate_stock_score 函数不存在")
    
    print("\n🧪 测试动态换仓决策逻辑...")
    
    # 测试动态换仓决策
    print("  模拟场景: 持仓已满，有新推荐股票")
    print("  决策规则: 如果新股票得分 > 最差持仓得分 × 1.2，执行换仓")
    
    # 模拟持仓得分
    position_scores = [
        {'stock_code': '000001', 'score': 5.0},
        {'stock_code': '000002', 'score': 3.0},
        {'stock_code': '000003', 'score': 1.0}
    ]
    
    # 找到最差持仓
    worst_position = min(position_scores, key=lambda x: x['score'])
    worst_score = worst_position['score']
    
    print(f"  最差持仓: {worst_position['stock_code']}, 得分: {worst_score:.2f}")
    
    # 测试不同新股票得分
    test_cases = [
        {'stock_code': '000005', 'score': 1.5, 'expected': True},   # 得分1.5 > 1.2*1.0=1.2
        {'stock_code': '000006', 'score': 1.3, 'expected': True},   # 得分1.3 > 1.2*1.0=1.2
        {'stock_code': '000007', 'score': 6.0, 'expected': True},   # 得分6.0 > 1.2*1.0=1.2
    ]
    
    for case in test_cases:
        should_swap = case['score'] > worst_score * 1.2
        status = "✅" if should_swap == case['expected'] else "❌"
        print(f"  {status} 新股票 {case['stock_code']} 得分: {case['score']:.2f}, 是否换仓: {should_swap} (预期: {case['expected']})")
    
    print("\n✅ 测试完成")

def test_backtest_logic():
    """测试回测逻辑"""
    print("\n🧪 测试回测逻辑结构...")
    
    # 创建回测系统
    backtest = BacktestSystem(
        initial_capital=50000,
        max_positions=3,
        max_price=150.0,
        start_date='2025-01-01'
    )
    
    # 检查关键方法
    required_methods = [
        '_get_strategy_recommendations',
        '_should_sell',
        '_execute_sell',
        '_execute_buy',
        '_record_daily_status',
        'run_backtest',
        'save_results'
    ]
    
    print("  检查关键方法是否存在:")
    for method in required_methods:
        if hasattr(backtest, method):
            print(f"    ✅ {method}")
        else:
            print(f"    ❌ {method}")
    
    # 检查交易规则参数
    print("\n  检查交易规则参数:")
    from backtest_system import (
        STOP_LOSS_RATE, TAKE_PROFIT_RATE, MAX_HOLD_DAYS,
        FEE_RATE, MIN_FEE
    )
    
    print(f"    止损率: {STOP_LOSS_RATE:.1%}")
    print(f"    止盈率: {TAKE_PROFIT_RATE:.1%}")
    print(f"    最大持有天数: {MAX_HOLD_DAYS}")
    print(f"    手续费率: {FEE_RATE:.6f}")
    print(f"    最低手续费: {MIN_FEE:.1f}元")
    
    print("\n✅ 回测逻辑测试完成")

def main():
    """主函数"""
    print("=" * 60)
    print("测试动态换仓逻辑")
    print("=" * 60)
    
    # 运行测试
    test_position_evaluation()
    test_backtest_logic()
    
    print("\n" + "=" * 60)
    print("所有测试完成")
    print("=" * 60)

if __name__ == "__main__":
    main()