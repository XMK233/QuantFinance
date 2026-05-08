#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
增量更新检测调试脚本
用于显示详细的检测过程和判断逻辑
"""

import sqlite3
from datetime import datetime, timedelta
from stock_database import StockDatabase

def debug_stock_update_check(stock_code: str = "sh.600004"):
    """调试单只股票的增量更新检测过程"""
    
    print(f"🔍 开始调试股票 {stock_code} 的增量更新检测")
    print("=" * 60)
    
    # 初始化数据库
    db = StockDatabase()
    
    # 获取当前时间信息
    now = datetime.now()
    print(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"星期: {['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]}")
    
    # 调试日线和周线的检测
    for freq_name, freq in [("日线", "daily"), ("周线", "weekly")]:
        print(f"\n📊 {freq_name}检测:")
        print("-" * 40)
        
        # 1. 获取数据库中最新日期
        max_date = db.get_max_date(stock_code, freq)
        print(f"数据库最新日期: {max_date or '无数据'}")
        
        if not max_date:
            print("❌ 数据库中无数据，需要完整下载")
            continue
        
        # 2. 获取最后一个交易日
        last_trading_day = db._get_last_trading_day()
        print(f"最后一个交易日: {last_trading_day}")
        
        # 3. 日期比较
        max_date_dt = datetime.strptime(max_date, '%Y-%m-%d').date()
        
        print(f"比较: 数据库最新日期({max_date_dt}) >= 最后交易日({last_trading_day})?")
        
        if max_date_dt >= last_trading_day:
            print("✅ 数据已是最新，无需更新")
            missing_dates = [max_date, max_date]
        else:
            print("🔄 需要更新数据")
            next_day = (datetime.strptime(max_date, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')
            missing_dates = [next_day, last_trading_day.strftime('%Y-%m-%d')]
        
        print(f"缺失日期范围: {missing_dates[0]} 到 {missing_dates[1]}")
        
        # 4. 最终判断
        if missing_dates[0] <= missing_dates[1] and missing_dates[0] != missing_dates[1]:
            # 对于周线，额外检查是否距离上一个周线日期超过一周
            if freq == "weekly" and max_date_dt:
                days_since_last_weekly = (last_trading_day - max_date_dt).days
                if days_since_last_weekly < 7:
                    print(f"✅ 周线数据: 距离上次更新仅 {days_since_last_weekly} 天，无需更新")
                else:
                    print(f"🎯 需要下载: {missing_dates[0]} 到 {missing_dates[1]}")
            else:
                print(f"🎯 需要下载: {missing_dates[0]} 到 {missing_dates[1]}")
        else:
            print("✅ 无需下载 (日期范围无效)")
    
    print("\n" + "=" * 60)
    print("🎯 调试完成")

def debug_multiple_stocks():
    """调试多只股票的检测过程"""
    
    print("🔍 调试多只股票的增量更新检测")
    print("=" * 60)
    
    db = StockDatabase()
    
    # 随机选择几只股票
    conn = sqlite3.connect(db.db_path)
    sample_stocks = conn.execute(
        "SELECT code FROM stocks ORDER BY RANDOM() LIMIT 5"
    ).fetchall()
    conn.close()
    
    for stock_code, in sample_stocks:
        print(f"\n📈 股票: {stock_code}")
        print("-" * 30)
        
        for freq_name, freq in [("日线", "daily"), ("周线", "weekly")]:
            max_date = db.get_max_date(stock_code, freq)
            last_trading_day = db._get_last_trading_day()
            
            status = "✅ 最新"
            if max_date:
                max_date_dt = datetime.strptime(max_date, '%Y-%m-%d').date()
                if max_date_dt < last_trading_day:
                    status = "🔄 需更新"
            else:
                status = "❌ 无数据"
            
            print(f"{freq_name}: {max_date or '无数据'} -> {status}")

def debug_trading_day_logic():
    """调试交易日判断逻辑"""
    
    print("🔍 调试交易日判断逻辑")
    print("=" * 60)
    
    db = StockDatabase()
    
    # 测试不同时间点的判断
    test_times = [
        ("周一 09:00", datetime(2025, 4, 7, 9, 0)),
        ("周一 14:00", datetime(2025, 4, 7, 14, 0)),
        ("周一 15:30", datetime(2025, 4, 7, 15, 30)),
        ("周六 10:00", datetime(2025, 4, 5, 10, 0)),
        ("周日 10:00", datetime(2025, 4, 6, 10, 0)),
    ]
    
    for desc, test_time in test_times:
        # 临时修改方法以使用测试时间
        original_now = datetime.now
        datetime.now = lambda: test_time
        
        try:
            last_trading_day = db._get_last_trading_day()
            print(f"{desc}: 最后一个交易日 = {last_trading_day}")
        finally:
            datetime.now = original_now

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='增量更新检测调试')
    parser.add_argument('--stock', default='sh.600004', help='股票代码')
    parser.add_argument('--multiple', action='store_true', help='调试多只股票')
    parser.add_argument('--trading-day', action='store_true', help='调试交易日逻辑')
    
    args = parser.parse_args()
    
    if args.trading_day:
        debug_trading_day_logic()
    elif args.multiple:
        debug_multiple_stocks()
    else:
        debug_stock_update_check(args.stock)