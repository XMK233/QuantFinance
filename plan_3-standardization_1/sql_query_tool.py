#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
SQL查询工具 - 执行SQL查询并返回pandas DataFrame
使用方法: 
    from sql_query_tool import query_sql
    result = query_sql("SELECT * FROM stocks LIMIT 5")
"""

import pandas as pd
import sqlite3
from typing import Optional

# 默认数据库路径（根据您的项目配置）
DEFAULT_DB_PATH = '/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_data.db'

def query_sql(sql: str, db_path: Optional[str] = None) -> pd.DataFrame:
    """
    执行SQL查询并返回pandas DataFrame
    
    参数:
        sql (str): SQL查询语句
        db_path (str, optional): 数据库文件路径，默认为项目数据库
        
    返回:
        pd.DataFrame: 查询结果，如果出错返回空的DataFrame
        
    示例:
        >>> result = query_sql("SELECT * FROM stocks LIMIT 5")
        >>> result = query_sql("SELECT code, name FROM stocks WHERE market='SH'", "custom.db")
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        
        # 执行SQL查询并返回DataFrame
        df = pd.read_sql_query(sql, conn)
        
        # 关闭连接
        conn.close()
        
        print(f"✅ 查询成功，返回 {len(df)} 行数据")
        return df
        
    except sqlite3.Error as e:
        print(f"❌ SQLite错误: {e}")
        return pd.DataFrame()
        
    except pd.errors.DatabaseError as e:
        print(f"❌ 数据库查询错误: {e}")
        return pd.DataFrame()
        
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return pd.DataFrame()

def get_table_info(table_name: str, db_path: Optional[str] = None) -> pd.DataFrame:
    """
    获取表结构信息
    
    参数:
        table_name (str): 表名
        db_path (str, optional): 数据库文件路径
        
    返回:
        pd.DataFrame: 表结构信息
    """
    sql = f"PRAGMA table_info({table_name})"
    return query_sql(sql, db_path)

def get_table_names(db_path: Optional[str] = None) -> pd.DataFrame:
    """
    获取数据库中所有表名
    
    参数:
        db_path (str, optional): 数据库文件路径
        
    返回:
        pd.DataFrame: 表名列表
    """
    sql = "SELECT name FROM sqlite_master WHERE type='table'"
    return query_sql(sql, db_path)

def query_with_params(sql: str, params: tuple, db_path: Optional[str] = None) -> pd.DataFrame:
    """
    执行带参数的SQL查询（防止SQL注入）
    
    参数:
        sql (str): SQL查询语句（使用?作为占位符）
        params (tuple): 参数元组
        db_path (str, optional): 数据库文件路径
        
    返回:
        pd.DataFrame: 查询结果
        
    示例:
        >>> result = query_with_params(
        ...     "SELECT * FROM stocks WHERE market = ? AND status = ?", 
        ...     ('SH', '1')
        ... )
    """
    if db_path is None:
        db_path = DEFAULT_DB_PATH
    
    try:
        conn = sqlite3.connect(db_path)
        df = pd.read_sql_query(sql, conn, params=params)
        conn.close()
        print(f"✅ 参数查询成功，返回 {len(df)} 行数据")
        return df
        
    except Exception as e:
        print(f"❌ 参数查询错误: {e}")
        return pd.DataFrame()

# 测试函数
def test_query():
    """测试SQL查询功能"""
    print("🔍 测试SQL查询工具...")
    
    # 1. 获取所有表名
    print("\n📊 数据库中的表:")
    tables = get_table_names()
    print(tables)
    
    # 2. 查询股票表的前5条记录
    if not tables.empty and 'stocks' in tables['name'].values:
        print("\n📈 stocks表的前5条记录:")
        result = query_sql("SELECT * FROM stocks LIMIT 5")
        print(result)
    
    # 3. 获取表结构
    print("\n🔧 stocks表结构:")
    table_info = get_table_info('stocks')
    print(table_info)
    
    print("\n✅ 测试完成!")

if __name__ == "__main__":
    test_query()