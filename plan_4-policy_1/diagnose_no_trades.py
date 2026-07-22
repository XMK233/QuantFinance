#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
诊断脚本：查找为什么回测系统没有交易
"""

import sys
from pathlib import Path

# 添加当前目录到路径
sys.path.insert(0, str(Path(__file__).parent))

def test_strategy_combinations():
    """测试策略组合是否能找到符合条件的股票"""
    print("🧪 测试策略组合...")
    
    try:
        from daily_trading_system import BaseOperator, STStockOperator
        from stock_operators.cross_ma_operator import CrossMAOperator
        
        base_op = BaseOperator()
        st_op = STStockOperator()
        cross_op = CrossMAOperator()
        
        # 获取所有股票代码
        all_codes = base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        print(f"  沪深主板股票数量: {len(all_codes)}")
        
        if not all_codes:
            print("  ❌ 无法获取股票代码")
            return False
        
        # 测试前20只股票
        test_codes = all_codes[:20]
        found_stocks = []
        
        for code in test_codes:
            print(f"\n  测试股票 {code}:")
            
            # 1. 检查ST状态
            st_info = st_op.calculate(code)
            is_st = st_info.get('is_st', False)
            print(f"    ST状态: {'是' if is_st else '否'}")
            if is_st:
                continue
            
            # 2. 检查cross_ma50策略
            cross_info = cross_op.calculate(code)
            cross_ma = cross_info.get('cross_ma_4w', False)
            print(f"    cross_ma50信号: {'是' if cross_ma else '否'}")
            if not cross_ma:
                continue
            
            # 3. 获取日线数据
            daily_data = base_op.get_daily_data(code, days=30)
            if daily_data is None or daily_data.empty or len(daily_data) < 6:
                print(f"    ❌ 日线数据不足")
                continue
            
            current_price = float(daily_data['close'].iloc[-1])
            print(f"    当前价格: {current_price:.2f}")
            
            # 4. 检查weekly_mean_down策略
            weekly_data = base_op.get_weekly_data(code, weeks=70)
            if weekly_data is None or weekly_data.empty or len(weekly_data) < 60:
                print(f"    ❌ 周线数据不足")
                continue
            
            weekly_data = weekly_data.sort_values('date')
            weekly_data['close'] = pd.to_numeric(weekly_data['close'], errors='coerce')
            weekly_data = weekly_data.dropna(subset=['close'])
            
            if len(weekly_data) < 60:
                print(f"    ❌ 周线数据不足60周")
                continue
            
            last60 = weekly_data['close'].tail(60)
            prev30 = last60.iloc[:30]
            recent30 = last60.iloc[30:]
            
            if prev30.empty or recent30.empty:
                print(f"    ❌ 周线数据分段失败")
                continue
            
            prev_mean = float(prev30.mean())
            recent_mean = float(recent30.mean())
            
            print(f"    前30周均价: {prev_mean:.2f}")
            print(f"    近30周均价: {recent_mean:.2f}")
            
            if not (prev_mean > 0 and recent_mean > 0):
                print(f"    ❌ 均价计算异常")
                continue
            
            if recent_mean < prev_mean:
                print(f"    ✅ 符合weekly_mean_down策略")
                found_stocks.append({
                    'code': code,
                    'price': current_price,
                    'prev_mean': prev_mean,
                    'recent_mean': recent_mean
                })
            else:
                print(f"    ❌ 不符合weekly_mean_down策略")
        
        print(f"\n📊 测试结果:")
        print(f"  测试股票数量: {len(test_codes)}")
        print(f"  符合条件的股票: {len(found_stocks)}")
        
        if found_stocks:
            print(f"\n✅ 找到的股票:")
            for stock in found_stocks:
                print(f"  {stock['code']}: 价格={stock['price']:.2f}, 前30周均价={stock['prev_mean']:.2f}, 近30周均价={stock['recent_mean']:.2f}")
            return True
        else:
            print(f"\n❌ 没有找到符合条件的股票")
            return False
            
    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_data_availability():
    """测试数据可用性"""
    print("\n📊 测试数据可用性...")
    
    try:
        from daily_trading_system import BaseOperator
        
        base_op = BaseOperator()
        
        # 测试几只常见股票
        test_codes = ['000001', '000002', '000858', '600519', '601318']
        
        for code in test_codes:
            print(f"\n  测试 {code}:")
            
            # 测试日线数据
            daily_data = base_op.get_daily_data(code, days=10)
            if daily_data is None or daily_data.empty:
                print(f"    ❌ 日线数据不可用")
            else:
                print(f"    ✅ 日线数据可用，最近价格: {float(daily_data['close'].iloc[-1]):.2f}")
            
            # 测试周线数据
            weekly_data = base_op.get_weekly_data(code, weeks=10)
            if weekly_data is None or weekly_data.empty:
                print(f"    ❌ 周线数据不可用")
            else:
                print(f"    ✅ 周线数据可用，最近价格: {float(weekly_data['close'].iloc[-1]):.2f}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 数据测试失败: {e}")
        return False

def test_backtest_system_directly():
    """直接测试回测系统"""
    print("\n⚡ 直接测试回测系统...")
    
    try:
        from accelerated_backtest import AcceleratedBacktestSystem
        
        print("  创建回测系统实例...")
        backtest = AcceleratedBacktestSystem(
            initial_capital=50000,
            max_positions=3,
            max_price=150.0,
            start_date="2025-01-01",
            use_gpu=False,
            num_workers=1
        )
        
        print(f"  交易日数量: {len(backtest.trading_dates)}")
        
        # 测试前5个交易日
        test_dates = backtest.trading_dates[:5]
        
        for date in test_dates:
            print(f"\n  测试日期: {date.date()}")
            
            # 获取策略推荐
            recommendations = backtest._get_strategy_recommendations_parallel(date)
            
            if recommendations.empty:
                print(f"    ❌ 没有策略推荐")
                print(f"    可能原因:")
                print(f"      1. 没有符合条件的股票")
                print(f"      2. 数据获取失败")
                print(f"      3. 策略条件太严格")
            else:
                print(f"    ✅ 找到 {len(recommendations)} 只推荐股票")
                for _, row in recommendations.iterrows():
                    print(f"      {row['stock_code']}: 价格={row['current_price']:.2f}, 得分={row.get('score', 0):.2f}")
        
        return True
        
    except Exception as e:
        print(f"  ❌ 回测系统测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """主函数"""
    print("🔍 诊断回测系统无交易问题")
    print("=" * 70)
    
    # 导入必要的库
    import pandas as pd
    
    # 运行诊断测试
    data_ok = test_data_availability()
    
    if data_ok:
        strategy_ok = test_strategy_combinations()
        
        if strategy_ok:
            print("\n✅ 策略组合测试通过，应该能找到符合条件的股票")
        else:
            print("\n❌ 策略组合测试失败，可能策略条件太严格或数据问题")
        
        # 直接测试回测系统
        backtest_ok = test_backtest_system_directly()
    
    # 总结
    print("\n" + "=" * 70)
    print("📋 诊断总结")
    print("=" * 70)
    
    print("可能的原因:")
    print("1. 📊 数据问题: 无法获取有效的日线或周线数据")
    print("2. 🎯 策略条件太严格: weekly_mean_down + cross_ma50 组合可能很少出现")
    print("3. ⚙️  系统配置: 价格限制（≤150元）可能过滤了太多股票")
    print("4. 🔧 代码逻辑: 策略推荐函数可能有bug")
    
    print("\n建议的解决方案:")
    print("1. 🔍 检查数据源: 确保能获取到有效的股票数据")
    print("2. 📈 放宽策略条件: 降低weekly_mean_down的要求")
    print("3. 💰 调整价格限制: 提高最高买入价格")
    print("4. 🐛 调试代码: 逐步检查策略推荐逻辑")
    
    print("=" * 70)

if __name__ == "__main__":
    main()