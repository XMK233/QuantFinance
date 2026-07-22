#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
每日数据更新脚本
自动更新股票数据并生成交易信号
"""

import argparse
from datetime import datetime, timedelta
from bao_data_downloader import BaoStockDownloader
import sqlite3

DEFAULT_DB = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_data.db"

def _get_db_max_date(conn: sqlite3.Connection, table_name: str) -> str | None:
    row = conn.execute(f"SELECT MAX(date) FROM {table_name}").fetchone()
    return row[0] if row and row[0] else None

def _count_weekly_stale_stocks(conn: sqlite3.Connection, expected_weekly: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*)
        FROM (
            SELECT s.code AS stock_code, w.max_date
            FROM stocks s
            LEFT JOIN (
                SELECT stock_code, MAX(date) AS max_date
                FROM stock_weekly
                GROUP BY stock_code
            ) w
            ON s.code = w.stock_code
        ) t
        WHERE t.max_date IS NULL OR t.max_date < ?
        """,
        (expected_weekly,),
    ).fetchone()
    return int(row[0]) if row and row[0] is not None else 0

def _get_last_trading_day():
    now = datetime.now()
    today = now.date()
    if today.weekday() == 5:
        return today - timedelta(days=1)
    if today.weekday() == 6:
        return today - timedelta(days=2)
    if now.hour >= 15 or (now.hour == 14 and now.minute >= 30):
        return today
    if today.weekday() == 0:
        return today - timedelta(days=3)
    return today - timedelta(days=1)

def _get_last_weekly_day(last_trading_day):
    delta = (last_trading_day.weekday() - 4) % 7
    return last_trading_day - timedelta(days=delta)

def update_daily_data(force_weekly: bool = False, concurrency_mode: str = 'process', max_workers: int = 6):
    """
    更新每日数据
    
    Args:
        force_weekly: 是否强制更新周线数据
        concurrency_mode: 并发模式，可选值：'single', 'thread', 'process'
        max_workers: 最大工作进程/线程数
    """
    print(f"📊 开始更新每日数据 (模式: {concurrency_mode}, 工作数: {max_workers})...")
    
    # 创建下载器实例
    downloader = BaoStockDownloader()
    
    try:
        # 登录
        print("🔐 登录baostock...")
        downloader.login()

        stock_list = downloader.get_stock_list()
        stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sz.30")]
        stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sh.688")]
        stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sh.689")]
        stock_list = stock_list[~stock_list["code_name"].astype(str).str.contains("ST", na=False)]
        
        # 更新股票基本信息（每周一次即可）
        if datetime.now().weekday() == 0:  # 每周一更新
            print("📈 更新股票基本信息...")
            downloader.update_stock_info()
        
        # 更新日线数据
        print("📅 更新日线数据...")
        success, count, message = downloader.incremental_update(
            frequency='d', 
            max_workers=max_workers, 
            stock_list=stock_list,
            concurrency_mode=concurrency_mode
        )
        
        if success:
            print(f"✅ 日线数据更新成功: {count} 条记录")
        else:
            print(f"❌ 日线数据更新失败: {message}")
        
        last_trading_day = _get_last_trading_day()
        expected_weekly = _get_last_weekly_day(last_trading_day)
        with sqlite3.connect(DEFAULT_DB) as conn:
            expected_weekly_str = expected_weekly.strftime("%Y-%m-%d")
            weekly_stale_count = _count_weekly_stale_stocks(conn, expected_weekly_str)

        need_weekly = force_weekly or weekly_stale_count > 0
        if need_weekly:
            print(f"📌 周线目标日期: {expected_weekly_str} | 待补全股票数: {weekly_stale_count}")
            print("📈 更新周线数据...")
            success, count, message = downloader.incremental_update(
                frequency='w', 
                max_workers=max_workers, 
                stock_list=stock_list,
                concurrency_mode=concurrency_mode
            )
            if success:
                print(f"✅ 周线数据更新成功: {count} 条记录")
            else:
                print(f"❌ 周线数据更新失败: {message}")
        else:
            print(f"✅ 周线数据已更新到: {expected_weekly_str}")
        
        print("✅ 数据更新完成")
        
    except Exception as e:
        print(f"❌ 数据更新出错: {e}")
    finally:
        # 登出
        downloader.logout()

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='每日数据更新脚本')
    parser.add_argument('--full', action='store_true', help='执行完整更新（包括周线）')
    parser.add_argument('--mode', type=str, default='process', 
                       choices=['single', 'thread', 'process'],
                       help='并发模式: single(单线程), thread(多线程), process(多进程，默认)')
    parser.add_argument('--workers', type=int, default=6,
                       help='工作进程/线程数 (默认: 6)')
    args = parser.parse_args()
    
    print(f"🎯 开始每日数据更新 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print(f"   📋 并发模式: {args.mode}")
    print(f"   👷 工作数量: {args.workers}")
    print(f"   📊 完整更新: {'是' if args.full else '否'}")
    print("-" * 50)
    
    # 更新数据
    update_daily_data(
        force_weekly=args.full,
        concurrency_mode=args.mode,
        max_workers=args.workers
    )
    
    print("-" * 50)
    print("✅ 每日数据更新完成")

if __name__ == "__main__":
    main()
