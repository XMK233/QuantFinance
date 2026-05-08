#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
一阳穿四线算子
检测在过去的2/4/8周内是否有过一阳穿四线模式
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class CrossMAOperator:
    """一阳穿四线检测算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算一阳穿四线特征
        
        Returns:
            Dict containing:
            - cross_ma_2w: 过去2周内是否有一阳穿四线
            - cross_ma_4w: 过去4周内是否有一阳穿四线  
            - cross_ma_8w: 过去8周内是否有一阳穿四线
        """
        # 获取周线数据
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=50)
        
        if weekly_data.empty:
            return {
                'cross_ma_2w': False,
                'cross_ma_4w': False,
                'cross_ma_8w': False
            }
        
        # 计算移动平均线（如果尚未计算）
        for window in [5, 10, 20, 30]:
            if f'ma{window}' not in weekly_data.columns:
                weekly_data[f'ma{window}'] = weekly_data['close'].rolling(window=window).mean()
        
        results = {}
        
        # 检查不同时间窗口
        for weeks in [2, 4, 8]:
            recent_data = weekly_data.tail(weeks)
            has_cross = self._check_cross_ma_pattern(recent_data)
            results[f'cross_ma_{weeks}w'] = has_cross
        
        return results
    
    def _check_cross_ma_pattern(self, data: pd.DataFrame) -> bool:
        """检查一阳穿四线模式"""
        if len(data) < 1:
            return False
        
        # 获取最新的一周数据
        latest_week = data.iloc[-1]
        
        # 检查是否阳线（收盘价高于开盘价）
        if latest_week['close'] <= latest_week['open']:
            return False
        
        # 检查是否穿越四条均线
        ma_columns = ['ma5', 'ma10', 'ma20', 'ma30']
        
        # 确保所有均线数据都存在
        for col in ma_columns:
            if col not in data.columns or pd.isna(latest_week[col]):
                return False
        
        # 检查收盘价是否同时高于四条均线
        close_above_all = all(latest_week['close'] > latest_week[ma] for ma in ma_columns)
        
        # 检查开盘价是否同时低于四条均线
        open_below_all = all(latest_week['open'] < latest_week[ma] for ma in ma_columns)
        
        return close_above_all and open_below_all


class ClosePriceOperator:
    """周收盘价算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        获取周收盘价原始数值
        
        Returns:
            Dict containing:
            - close_price: 最新周收盘价
            - close_price_1w_ago: 一周前收盘价
            - close_price_4w_ago: 四周前收盘价
        """
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=5)
        
        if weekly_data.empty:
            return {
                'close_price': None,
                'close_price_1w_ago': None,
                'close_price_4w_ago': None
            }
        
        # 按日期排序（确保最新数据在最后）
        weekly_data = weekly_data.sort_values('date')
        
        return {
            'close_price': weekly_data.iloc[-1]['close'] if len(weekly_data) >= 1 else None,
            'close_price_1w_ago': weekly_data.iloc[-2]['close'] if len(weekly_data) >= 2 else None,
            'close_price_4w_ago': weekly_data.iloc[-5]['close'] if len(weekly_data) >= 5 else None
        }