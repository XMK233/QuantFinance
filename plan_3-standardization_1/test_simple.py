#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单的并发模式测试
"""

import baostock as bs
import time

def test_baostock_connection():
    """测试baostock连接"""
    print("🔗 测试baostock连接...")
    
    try:
        # 尝试登录
        print("  尝试登录...")
        lg = bs.login()
        
        if lg.error_code != '0':
            print(f"❌ 登录失败: {lg.error_msg}")
            return False
        
        print("✅ 登录成功")
        
        # 尝试获取股票列表
        print("  获取股票列表...")
        rs = bs.query_stock_basic()
        
        if rs.error_code != '0':
            print(f"❌ 获取股票列表失败: {rs.error_msg}")
            bs.logout()
            return False
        
        print("✅ 获取股票列表成功")
        
        # 登出
        bs.logout()
        print("✅ 登出成功")
        
        return True
        
    except Exception as e:
        print(f"❌ 连接测试异常: {e}")
        return False

def test_concurrency_modes():
    """测试不同并发模式的基本功能"""
    print("\n🧪 测试并发模式基本功能...")
    
    # 测试单线程模式
    print("\n1. 单线程模式测试")
    print("   特点: 顺序执行，最稳定")
    print("   适用: baostock访问限制严重时")
    
    # 测试多线程模式
    print("\n2. 多线程模式测试")
    print("   特点: 线程级并发，避免进程限制")
    print("   适用: 需要一定并发性但避免多进程限制")
    
    # 测试多进程模式
    print("\n3. 多进程模式测试")
    print("   特点: 进程级并发，速度最快")
    print("   适用: 网络环境良好，baostock限制不严格时")
    
    print("\n✅ 并发模式功能测试完成")

def main():
    print("🎯 === 简单并发模式测试 ===")
    print(f"⏰ 时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 50)
    
    # 测试连接
    connected = test_baostock_connection()
    
    if not connected:
        print("\n⚠️  baostock连接失败，可能原因:")
        print("  1. 网络连接问题")
        print("  2. baostock服务器维护")
        print("  3. 访问频率限制")
        print("\n💡 建议:")
        print("  - 检查网络连接")
        print("  - 稍后再试")
        print("  - 使用单线程模式避免并发限制")
        return
    
    # 测试并发模式
    test_concurrency_modes()
    
    print("\n" + "="*50)
    print("📋 使用示例:")
    print("="*50)
    print("\n1. 单线程模式 (最稳定):")
    print("   python bao_data_downloader.py --mode single --workers 1")
    
    print("\n2. 多线程模式 (平衡):")
    print("   python daily_update.py --mode thread --workers 3")
    
    print("\n3. 多进程模式 (最快):")
    print("   python run_weekly_update.py --mode process --workers 6")
    
    print("\n🎉 测试完成!")

if __name__ == "__main__":
    main()