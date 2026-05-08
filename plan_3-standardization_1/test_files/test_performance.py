#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import baostock as bs
from bao_data_downloader import BaoStockDownloader

def test_original_method():
    """测试原始 bao_get_single_stock.py 的方法"""
    print("🧪 测试原始下载方法性能...")
    
    # 登录 baostock
    bs.login()
    
    start_time = time.time()
    
    # 测试下载几只股票
    test_codes = ['sh.600000', 'sz.000001', 'sh.600036', 'sz.000002', 'sh.601318']
    
    for code in test_codes:
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg",
            start_date="2025-01-01", 
            end_date="2025-04-08",
            frequency="w", 
            adjustflag="2"
        )
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        print(f"  {code}: 下载了 {len(data_list)} 条数据")
    
    end_time = time.time()
    bs.logout()
    
    duration = end_time - start_time
    print(f"✅ 原始方法完成时间: {duration:.2f} 秒")
    return duration

def test_optimized_method():
    """测试优化后的方法性能"""
    print("🧪 测试优化后下载方法性能...")
    
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        start_time = time.time()
        
        # 测试下载同样的几只股票
        test_codes = ['sh.600000', 'sz.000001', 'sh.600036', 'sz.000002', 'sh.601318']
        
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
        print(f"✅ 优化方法完成时间: {duration:.2f} 秒")
        return duration
        
    except Exception as e:
        print(f"❌ 测试出错: {e}")
        return None
    finally:
        downloader.logout()

def main():
    print("📊 性能对比测试开始")
    print("=" * 50)
    
    # 测试原始方法
    original_time = test_original_method()
    
    print("\n" + "=" * 50)
    
    # 测试优化方法
    optimized_time = test_optimized_method()
    
    print("\n" + "=" * 50)
    
    if original_time is not None and optimized_time is not None:
        speedup = original_time / optimized_time
        print(f"🚀 性能提升: {speedup:.2f} 倍")
        
        if speedup > 1:
            print("✅ 优化成功！性能有所提升")
        else:
            print("⚠️  性能没有提升，需要进一步优化")
    
    print("📊 性能对比测试完成")

if __name__ == "__main__":
    main()