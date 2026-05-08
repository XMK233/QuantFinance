#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
每周五收盘后运行的股票数据增量更新脚本
使用方法: python run_weekly_update.py
"""

import argparse
from datetime import datetime
from bao_data_downloader import BaoStockDownloader

def main():
    parser = argparse.ArgumentParser(description='股票数据增量更新脚本')
    parser.add_argument('--db', default=None, help='数据库文件路径（默认在数据目录）')
    parser.add_argument('--workers', type=int, default=4, help='并发进程数')
    parser.add_argument('--test', action='store_true', help='测试模式，只处理少量股票')
    parser.add_argument('--debug', action='store_true', help='调试模式，显示详细检测信息')
    args = parser.parse_args()
    
    from tqdm import tqdm
    import time
    
    print(f"🎯 === 股票数据增量更新开始 ===")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"💾 数据库: {args.db}")
    print(f"⚡ 并发数: {args.workers}")
    print("-" * 50)
    
    downloader = BaoStockDownloader(args.db)
    
    try:
        # 显示登录进度
        with tqdm(total=100, desc="登录baostock", bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed}") as pbar:
            downloader.login()
            pbar.update(100)
        
        # 1. 更新股票基本信息（支持缓存复用）
        print("\n📋 1. 更新股票基本信息")
        stock_list = downloader.update_stock_info()
        
        # 测试模式：只处理前10只股票
        if args.test:
            print("🔬 测试模式：只处理前10只股票")
            stock_list = stock_list.head(10)
        
        # 2. 增量更新日线数据
        print("\n📈 2. 增量更新日线数据")
        downloader.incremental_update('d', max_workers=args.workers, stock_list=stock_list, debug_mode=args.debug)
        
        # 3. 增量更新周线数据
        print("\n📊 3. 增量更新周线数据")
        downloader.incremental_update('w', max_workers=args.workers, stock_list=stock_list, debug_mode=args.debug)
        
        print(f"\n✅ === 更新完成 ===")
        print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎉 所有数据已成功更新到数据库！")
        
    except Exception as e:
        print(f"\n❌ !!! 更新失败: {e}")
        
    finally:
        # 显示登出进度
        with tqdm(total=100, desc="登出系统", bar_format="{desc}: {percentage:3.0f}%|{bar}| {elapsed}") as pbar:
            downloader.logout()
            pbar.update(100)

if __name__ == "__main__":
    main()
