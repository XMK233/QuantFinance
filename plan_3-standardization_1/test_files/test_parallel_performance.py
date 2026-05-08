#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import baostock as bs
from bao_data_downloader import BaoStockDownloader

def test_parallel_download():
    """测试并行下载性能"""
    print("🧪 测试并行下载性能...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 获取股票列表
        stock_list = downloader.get_stock_list()
        test_codes = stock_list['code'].head(10).tolist()  # 只测试前10只股票
        
        print(f"测试 {len(test_codes)} 只股票的并行下载性能")
        
        # 测试并行下载
        start_time = time.time()
        
        # 使用并行下载
        downloader.incremental_update('w', max_workers=6, stock_list=stock_list.head(10))
        
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✅ 并行下载完成时间: {duration:.2f} 秒")
        return duration
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        return None
    finally:
        downloader.logout()

def test_serial_download():
    """测试串行下载性能"""
    print("🧪 测试串行下载性能...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 获取股票列表
        stock_list = downloader.get_stock_list()
        test_codes = stock_list['code'].head(10).tolist()  # 只测试前10只股票
        
        print(f"测试 {len(test_codes)} 只股票的串行下载性能")
        
        start_time = time.time()
        
        # 串行下载
        for code in test_codes:
            df, msg = downloader.download_stock_data(
                code, 
                frequency='w',
                start_date='2025-01-01',
                end_date='2025-04-08'
            )
            if df is not None:
                print(f"  {code}: 下载了 {len(df)} 条数据")
            else:
                print(f"  {code}: {msg}")
        
        end_time = time.time()
        
        duration = end_time - start_time
        print(f"✅ 串行下载完成时间: {duration:.2f} 秒")
        return duration
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        return None
    finally:
        downloader.logout()

def main():
    print("📊 并行 vs 串行性能对比测试")
    print("=" * 60)
    
    # 测试串行下载
    # serial_time = test_serial_download()
    
    print("\n" + "=" * 60)
    
    # 测试并行下载
    parallel_time = test_parallel_download()
    
    print("\n" + "=" * 60)
    
    if serial_time is not None and parallel_time is not None:
        speedup = serial_time / parallel_time
        print(f"🚀 并行 vs 串行性能提升: {speedup:.2f} 倍")
        
        if speedup > 1:
            print("✅ 并行下载优化成功！性能大幅提升")
        else:
            print("⚠️  并行下载性能没有提升，需要进一步优化")
    
    print("📊 性能对比测试完成")

if __name__ == "__main__":
    main()