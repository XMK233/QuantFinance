#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
放量突破算子
检测75周周期内放量突破20周线的次数
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class VolumeBreakOperator:
    """放量突破算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算放量突破特征
        
        Returns:
            Dict containing:
            - volume_break_count: 75周内放量突破20周线的次数
            - volume_break_ge_2: 放量突破次数是否大于等于2次
        """
        # 获取75周的数据
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=75)
        
        if weekly_data.empty:
            return {
                'volume_break_count': 0,
                'volume_break_ge_2': False
            }
        
        # 计算移动平均线
        weekly_data['ma20'] = weekly_data['close'].rolling(window=20).mean()
        weekly_data['volume_ma20'] = weekly_data['volume'].rolling(window=20).mean()
        
        # 计算放量突破次数
        break_count = self._count_volume_breakthroughs(weekly_data)
        
        return {
            'volume_break_count': break_count,
            'volume_break_ge_2': break_count >= 2
        }
    
    def _count_volume_breakthroughs(self, data: pd.DataFrame) -> int:
        """计算放量突破20周线的次数"""
        count = 0
        
        for i in range(20, len(data)):  # 从第20周开始（确保有ma20数据）
            current_week = data.iloc[i]
            prev_week = data.iloc[i-1]
            
            # 检查是否突破20周线
            breakthrough = (current_week['close'] > current_week['ma20'] and 
                          prev_week['close'] <= prev_week['ma20'])
            
            # 检查是否放量（成交量大于20周平均成交量的1.5倍）
            volume_break = (current_week['volume'] > current_week['volume_ma20'] * 1.5)
            
            if breakthrough and volume_break:
                count += 1
        
        return count


class MADivergenceOperator:
    """均线发散算子"""
    
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)
    
    def calculate(self, stock_code: str) -> Dict[str, Any]:
        """
        计算均线发散特征
        
        Returns:
            Dict containing:
            - ma_divergence: 5、10、20周均线是否发散走多
        """
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=20)
        
        if weekly_data.empty:
            return {'ma_divergence': False}
        
        # 计算移动平均线
        for window in [5, 10, 20]:
            if f'ma{window}' not in weekly_data.columns:
                weekly_data[f'ma{window}'] = weekly_data['close'].rolling(window=window).mean()
        
        # 检查均线发散
        is_divergent = self._check_ma_divergence(weekly_data)
        
        return {'ma_divergence': is_divergent}
    
    def _check_ma_divergence(self, data: pd.DataFrame) -> bool:
        """检查均线是否发散走多"""
        if len(data) < 3:  # 至少需要3周数据
            return False
        
        # 获取最近三周的均线数据
        recent_data = data.tail(3)
        
        # 检查均线排列：ma5 > ma10 > ma20
        for i in range(len(recent_data)):
            week_data = recent_data.iloc[i]
            
            if not (week_data['ma5'] > week_data['ma10'] > week_data['ma20']):
                return False
        
        # 检查均线向上发散
        last_week = recent_data.iloc[-1]
        prev_week = recent_data.iloc[-2]
        
        # 所有均线都在上涨
        ma_rising = (last_week['ma5'] > prev_week['ma5'] and
                    last_week['ma10'] > prev_week['ma10'] and
                    last_week['ma20'] > prev_week['ma20'])
        
        return ma_rising