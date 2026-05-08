#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周线新高突破算子
检测是否突破近20周新高，及是否伴随放量
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class WeeklyBreakoutOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=60)
        if weekly_data.empty or len(weekly_data) < 25:
            return {
                "weekly_breakout_20w": False,
                "weekly_breakout_20w_volume": False,
            }

        weekly_data = weekly_data.sort_values("date")
        weekly_data["high_20w_prev"] = weekly_data["high"].rolling(window=20).max().shift(1)
        weekly_data["volume_ma20"] = weekly_data["volume"].rolling(window=20).mean()
        weekly_data["ma20"] = weekly_data["close"].rolling(window=20).mean()

        last = weekly_data.iloc[-1]
        prev_high = last.get("high_20w_prev")
        if pd.isna(prev_high) or prev_high <= 0:
            return {
                "weekly_breakout_20w": False,
                "weekly_breakout_20w_volume": False,
            }

        breakout = bool(last["close"] > float(prev_high))
        volume_ok = False
        try:
            vma = float(last["volume_ma20"])
            volume_ok = (vma > 0) and (float(last["volume"]) > vma * 1.2)
        except Exception:
            volume_ok = False

        trend_ok = False
        try:
            ma20 = float(last["ma20"])
            trend_ok = (ma20 > 0) and (float(last["close"]) > ma20)
        except Exception:
            trend_ok = False

        return {
            "weekly_breakout_20w": breakout and trend_ok,
            "weekly_breakout_20w_volume": breakout and trend_ok and volume_ok,
        }

