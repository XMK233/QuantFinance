#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试不同并发模式的功能
"""

import argparse
import time
from datetime import datetime
from bao_data_downloader import BaoStockDownloader

def test_single_mode():
    """测试单线程模式"""
    print("🧪 测试单线程模式...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 获取股票列表
        stock_list = downloader.get_stock_list()
        test_codes = stock_list['code'].head(5).tolist()  # 只测试前5只股票
        
        print(f"测试 {len(test_codes)} 只股票的单线程下载")
        
        # 测试单线程下载
        start_time = time.time()
        
        # 使用单线程模式
        success, data_count, msg = downloader.incremental_update(
            frequency='d', 
            max_workers=1,
            stock_list=stock_list.head(5),
            concurrency_mode='single',
            debug_mode=True
        )
        
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✅ 单线程下载完成时间: {duration:.2f} 秒")
        print(f"📊 结果: {msg}")
        
        return duration, success
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return None, False
    finally:
        downloader.logout()

def test_thread_mode(workers=2):
    """测试多线程模式"""
    print(f"🧪 测试多线程模式 (工作线程: {workers})...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 获取股票列表
        stock_list = downloader.get_stock_list()
        test_codes = stock_list['code'].head(10).tolist()  # 只测试前10只股票
        
        print(f"测试 {len(test_codes)} 只股票的多线程下载")
        
        # 测试多线程下载
        start_time = time.time()
        
        # 使用多线程模式
        success, data_count, msg = downloader.incremental_update(
            frequency='d', 
            max_workers=workers,
            stock_list=stock_list.head(10),
            concurrency_mode='thread',
            debug_mode=True
        )
        
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✅ 多线程下载完成时间: {duration:.2f} 秒")
        print(f"📊 结果: {msg}")
        
        return duration, success
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return None, False
    finally:
        downloader.logout()

def test_process_mode(workers=2):
    """测试多进程模式"""
    print(f"🧪 测试多进程模式 (工作进程: {workers})...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 获取股票列表
        stock_list = downloader.get_stock_list()
        test_codes = stock_list['code'].head(10).tolist()  # 只测试前10只股票
        
        print(f"测试 {len(test_codes)} 只股票的多进程下载")
        
        # 测试多进程下载
        start_time = time.time()
        
        # 使用多进程模式
        success, data_count, msg = downloader.incremental_update(
            frequency='d', 
            max_workers=workers,
            stock_list=stock_list.head(10),
            concurrency_mode='process',
            debug_mode=True
        )
        
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✅ 多进程下载完成时间: {duration:.2f} 秒")
        print(f"📊 结果: {msg}")
        
        return duration, success
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        import traceback
        traceback.print_exc()
        return None, False
    finally:
        downloader.logout()

def main():
    parser = argparse.ArgumentParser(description='测试不同并发模式')
    parser.add_argument('--mode', type=str, default='all',
                       choices=['single', 'thread', 'process', 'all'],
                       help='测试模式: single(单线程), thread(多线程), process(多进程), all(全部)')
    parser.add_argument('--workers', type=int, default=2,
                       help='工作进程/线程数 (默认: 2)')
    parser.add_argument('--skip-process', action='store_true',
                       help='跳过多进程测试（避免baostock限制）')
    
    args = parser.parse_args()
    
    print(f"🎯 === 并发模式测试开始 ===")
    print(f"⏰ 时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"📋 测试模式: {args.mode}")
    print(f"👷 工作数量: {args.workers}")
    print("-" * 60)
    
    results = {}
    
    # 根据选择的模式进行测试
    if args.mode in ['single', 'all']:
        print("\n" + "="*50)
        duration, success = test_single_mode()
        results['single'] = {'duration': duration, 'success': success}
    
    if args.mode in ['thread', 'all']:
        print("\n" + "="*50)
        duration, success = test_thread_mode(args.workers)
        results['thread'] = {'duration': duration, 'success': success}
    
    if args.mode in ['process', 'all'] and not args.skip_process:
        print("\n" + "="*50)
        duration, success = test_process_mode(args.workers)
        results['process'] = {'duration': duration, 'success': success}
    
    # 显示测试结果汇总
    print("\n" + "="*60)
    print("📊 测试结果汇总")
    print("="*60)
    
    for mode, result in results.items():
        if result['duration'] is not None:
            print(f"  {mode.upper():10} | 时间: {result['duration']:.2f}秒 | 成功: {result['success']}")
        else:
            print(f"  {mode.upper():10} | 时间: N/A | 成功: {result['success']}")
    
    print("\n🎉 并发模式测试完成!")
    
    # 提供使用建议
    print("\n💡 使用建议:")
    print("  - 如果遇到baostock访问限制，请使用 --mode single 或 --mode thread")
    print("  - 单线程模式最稳定，但速度最慢")
    print("  - 多线程模式在避免baostock限制的同时提供一定并发性")
    print("  - 多进程模式速度最快，但可能触发baostock限制")

if __name__ == "__main__":
    main()