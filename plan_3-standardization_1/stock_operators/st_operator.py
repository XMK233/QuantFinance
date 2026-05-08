#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ST股判断算子
检测股票是否为ST股
"""

import re
import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class STStockOperator:
    """ST股判断算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        判断是否为ST股
        
        Returns:
            Dict containing:
            - is_st: 是否为ST股
        """
        stock_info = self.base_operator.get_stock_info(stock_code)
        
        if not stock_info:
            return {'is_st': False}
        
        # 从股票名称判断是否为ST股
        stock_name = stock_info.get('name', '')
        
        # ST股通常名称中包含"ST"、"*ST"等标记
        is_st = self._is_st_stock(stock_name)
        
        return {'is_st': is_st}
    
    def _is_st_stock(self, stock_name: str) -> bool:
        """判断股票名称是否为ST股"""
        if not stock_name:
            return False
        
        # ST股名称模式
        st_patterns = [
            r'^ST',
            r'^\*ST', 
            r'^SST',
            r'^\*\*ST',
            r'ST$',
            r'\*ST$',
            r'退市',
            r'风险警示'
        ]
        
        for pattern in st_patterns:
            if re.search(pattern, stock_name):
                return True
        
        return False


class LimitUpOperator:
    """涨停相关算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算涨停相关特征
        
        Returns:
            Dict containing:
            - has_limit_up: 最近一周日线是否有过涨停
            - has_limit_up_pullback: 最近一周日线是否有过涨停回调
        """
        # 获取最近20天的日线数据（足够覆盖一周）
        daily_data = self.base_operator.get_daily_data(stock_code, days=20)
        
        if daily_data.empty:
            return {
                'has_limit_up': False,
                'has_limit_up_pullback': False
            }
        
        # 获取最近一周的数据
        recent_week_data = daily_data.tail(5)  # 5个交易日为一周
        
        has_limit_up = self._check_limit_up(recent_week_data)
        has_pullback = self._check_limit_up_pullback(recent_week_data)
        
        return {
            'has_limit_up': has_limit_up,
            'has_limit_up_pullback': has_pullback
        }
    
    def _check_limit_up(self, data: pd.DataFrame) -> bool:
        """检查是否有涨停"""
        for _, row in data.iterrows():
            if self._is_limit_up(row):
                return True
        return False
    
    def _check_limit_up_pullback(self, data: pd.DataFrame) -> bool:
        """检查是否有涨停回调"""
        if len(data) < 2:
            return False
        
        for i in range(len(data) - 1):
            current_day = data.iloc[i]
            next_day = data.iloc[i + 1]
            
            # 前一天涨停，后一天下跌
            if (self._is_limit_up(current_day) and 
                next_day['close'] < next_day['open'] and
                next_day['close'] < current_day['close']):
                return True
        
        return False
    
    def _is_limit_up(self, row) -> bool:
        """判断是否为涨停"""
        # 涨停通常表现为收盘价等于最高价，且涨幅接近10%
        return (abs(row['close'] - row['high']) < 0.01 and
                row['close'] > row['open'] and
                (row['close'] - row['open']) / row['open'] > 0.095)  # 涨幅大于9.5%