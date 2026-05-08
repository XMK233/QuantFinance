#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
基础算子类
提供数据库连接和基础数据获取功能
"""

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional


class BaseOperator:
    """基础算子类"""
    
    def __init__(self, db_path: str = None):
        """
        初始化算子
        
        Args:
            db_path: 数据库文件路径，如果为None则使用默认路径
        """
        if db_path is None:
            # 默认数据库路径
            self.db_path = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_data.db"
        else:
            self.db_path = db_path
    
    def get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def get_weekly_data(self, stock_code: str, weeks: int = 75) -> pd.DataFrame:
        """获取股票的周线数据"""
        query = f"""
        SELECT date, stock_code, open, high, low, close, volume, amount
        FROM stock_weekly 
        WHERE stock_code = ? 
        ORDER BY date DESC 
        LIMIT ?
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(stock_code, weeks))
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')  # 按日期升序排列
            
            # 计算移动平均线
            for window in [5, 10, 20, 30]:
                df[f'ma{window}'] = df['close'].rolling(window=window).mean()
            
            # 计算成交量均值
            df['volume_ma20'] = df['volume'].rolling(window=20).mean()
        
        return df
    
    def get_daily_data(self, stock_code: str, days: int = 20) -> pd.DataFrame:
        """获取股票的日线数据"""
        query = f"""
        SELECT date, stock_code, open, high, low, close, volume, amount
        FROM stock_daily 
        WHERE stock_code = ? 
        ORDER BY date DESC 
        LIMIT ?
        """
        
        with self.get_connection() as conn:
            df = pd.read_sql_query(query, conn, params=(stock_code, days))
        
        if not df.empty:
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date')  # 按日期升序排列
        
        return df
    
    def get_stock_info(self, stock_code: str) -> Dict[str, Any]:
        """获取股票基本信息"""
        query = """
        SELECT code, name, industry, market, listing_date
        FROM stocks 
        WHERE code = ?
        """
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, (stock_code,))
            result = cursor.fetchone()
        
        if result:
            return {
                'code': result[0],
                'name': result[1],
                'industry': result[2],
                'market': result[3],
                'listing_date': result[4]
            }
        return {}
    
    def get_all_stock_codes(self, exclude_gem: bool = True, exclude_star: bool = True) -> List[str]:
        """
        获取所有股票代码
        
        Args:
            exclude_gem: 是否排除创业板股票（默认True）
            exclude_star: 是否排除科创板股票（默认True）
        """
        # 首先尝试从数据库获取
        try:
            query = "SELECT code FROM stocks"
            with self.get_connection() as conn:
                df = pd.read_sql_query(query, conn)
            
            stock_codes = df['code'].tolist() if not df.empty else []
            
            if stock_codes:
                stock_codes = [code for code in stock_codes if code.startswith('sh.') or code.startswith('sz.')]
                if exclude_gem:
                    stock_codes = [code for code in stock_codes if not code.startswith('sz.30')]
                if exclude_star:
                    stock_codes = [code for code in stock_codes if not code.startswith('sh.688') and not code.startswith('sh.689')]
                
            return stock_codes
            
        except:
            # 如果数据库查询失败，回退到CSV文件
            return self._get_stock_codes_from_csv(exclude_gem, exclude_star)
    
    def _get_stock_codes_from_csv(self, exclude_gem: bool = True, exclude_star: bool = True) -> List[str]:
        """从CSV文件获取股票代码（兼容模式）"""
        try:
            csv_path = "/mnt/d/forCoding_code/QuantFinance/plan_1-select_stock_by_week/all_stock_list.csv"
            df = pd.read_csv(csv_path)
            
            # 过滤条件：正常状态(type=1)的股票
            if 'type' in df.columns and 'status' in df.columns:
                df = df[(df['type'] == 1) & (df['status'] == 1)]
            
            # 排除创业板股票
            if exclude_gem:
                df = df[~df['code'].str.startswith('sz.30')]

            if exclude_star:
                df = df[~(df['code'].str.startswith('sh.688') | df['code'].str.startswith('sh.689'))]
            
            return df['code'].tolist()
            
        except Exception as e:
            print(f"从CSV获取股票代码出错: {e}")
            return []


class FeatureCalculator:
    """特征计算器"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
        self.operators = []
    
    def register_operator(self, operator):
        """注册特征算子"""
        self.operators.append(operator)
    
    def calculate_features(self, stock_code: str) -> Dict[str, Any]:
        """计算单个股票的所有特征"""
        features = {'code': stock_code}
        
        for operator in self.operators:
            try:
                result = operator.calculate(stock_code)
                features.update(result)
            except Exception as e:
                print(f"计算股票 {stock_code} 的特征时出错: {e}")
                features.update({f"error_{operator.__class__.__name__}": str(e)})
        
        return features
    
    def calculate_all_stocks(self) -> pd.DataFrame:
        """计算所有股票的特征"""
        stock_codes = self.base_operator.get_all_stock_codes()
        results = []
        
        for code in stock_codes:
            features = self.calculate_features(code)
            results.append(features)
        
        return pd.DataFrame(results)
