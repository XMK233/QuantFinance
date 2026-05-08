#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
突破回调算子
检测最近一次突破20周均线后的回调情况
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class BreakthroughPullbackOperator:
    """突破回调算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算突破回调特征
        
        Returns:
            Dict containing:
            - breakthrough_pullback: 最近突破后是否有缩量回调且不跌破突破周收盘价
        """
        # 获取足够的周线数据
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=30)
        
        if weekly_data.empty:
            return {'breakthrough_pullback': False}
        
        # 计算移动平均线
        weekly_data['ma20'] = weekly_data['close'].rolling(window=20).mean()
        weekly_data['volume_ma20'] = weekly_data['volume'].rolling(window=20).mean()
        
        # 查找最近的突破
        breakthrough_week = self._find_recent_breakthrough(weekly_data)
        
        if breakthrough_week is None:
            return {'breakthrough_pullback': False}
        
        # 检查突破后的回调情况
        has_pullback = self._check_pullback_after_breakthrough(weekly_data, breakthrough_week)
        
        return {'breakthrough_pullback': has_pullback}
    
    def _find_recent_breakthrough(self, data: pd.DataFrame) -> int:
        """查找最近的突破20周线的周"""
        for i in range(len(data)-1, 0, -1):
            if i < 1:
                continue
                
            current_week = data.iloc[i]
            prev_week = data.iloc[i-1]
            
            # 突破条件：当前周收盘价高于20周线，且前一周收盘价低于20周线
            if (current_week['close'] > current_week['ma20'] and 
                prev_week['close'] <= prev_week['ma20']):
                return i
        
        return None
    
    def _check_pullback_after_breakthrough(self, data: pd.DataFrame, breakthrough_index: int) -> bool:
        """检查突破后的回调情况"""
        if breakthrough_index is None or breakthrough_index >= len(data) - 1:
            return False
        
        breakthrough_week = data.iloc[breakthrough_index]
        breakthrough_close = breakthrough_week['close']
        
        # 检查突破后几周的情况
        for i in range(breakthrough_index + 1, min(breakthrough_index + 4, len(data))):
            current_week = data.iloc[i]
            
            # 检查是否缩量（成交量小于突破周成交量）
            volume_shrink = current_week['volume'] < breakthrough_week['volume']
            
            # 检查是否不跌破突破周收盘价
            not_below_breakthrough = current_week['close'] >= breakthrough_close
            
            # 如果有回调（价格下跌）但未跌破突破价且缩量
            if (current_week['close'] < current_week['open'] and  # 下跌周
                volume_shrink and 
                not_below_breakthrough):
                return True
        
        return False


class ListingDateOperator:
    """上市日期算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算上市日期特征
        
        Returns:
            Dict containing:
            - listing_days: 上市天数
            - listing_gt_240: 上市是否大于240天
        """
        stock_info = self.base_operator.get_stock_info(stock_code)
        
        if not stock_info or 'listing_date' not in stock_info:
            return {
                'listing_days': None,
                'listing_gt_240': False
            }
        
        listing_date_str = stock_info['listing_date']
        
        if not listing_date_str:
            return {
                'listing_days': None,
                'listing_gt_240': False
            }
        
        try:
            # 转换上市日期
            listing_date = pd.to_datetime(listing_date_str)
            current_date = pd.to_datetime('today')
            
            # 计算上市天数
            listing_days = (current_date - listing_date).days
            
            return {
                'listing_days': listing_days,
                'listing_gt_240': listing_days > 240
            }
            
        except:
            return {
                'listing_days': None,
                'listing_gt_240': False
            }