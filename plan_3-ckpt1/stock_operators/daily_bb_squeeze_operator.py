#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日线布林带挤压突破算子
检测是否处于布林带挤压状态，以及是否向上突破上轨
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class DailyBBSqueezeOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=80)
        if daily_data.empty or len(daily_data) < 40:
            return {
                "bb_width": None,
                "bb_squeeze": False,
                "bb_breakout": False,
                "bb_squeeze_breakout": False,
            }

        daily_data = daily_data.sort_values("date").copy()
        daily_data["ma20"] = daily_data["close"].rolling(20).mean()
        daily_data["std20"] = daily_data["close"].rolling(20).std(ddof=0)
        daily_data["upper"] = daily_data["ma20"] + 2 * daily_data["std20"]
        daily_data["lower"] = daily_data["ma20"] - 2 * daily_data["std20"]
        daily_data["bb_width"] = (daily_data["upper"] - daily_data["lower"]) / daily_data["ma20"]
        daily_data["volume_ma20"] = daily_data["volume"].rolling(20).mean()

        last = daily_data.iloc[-1]
        width = last.get("bb_width")
        if pd.isna(width):
            return {
                "bb_width": None,
                "bb_squeeze": False,
                "bb_breakout": False,
                "bb_squeeze_breakout": False,
            }

        recent_width = daily_data["bb_width"].tail(40)
        width_min = recent_width.min()
        squeeze = bool(float(width) <= float(width_min) * 1.2) if pd.notna(width_min) else False

        breakout = False
        try:
            upper = float(last["upper"])
            breakout = float(last["close"]) > upper
        except Exception:
            breakout = False

        volume_ok = False
        try:
            vma = float(last["volume_ma20"])
            volume_ok = (vma > 0) and (float(last["volume"]) > vma * 1.2)
        except Exception:
            volume_ok = False

        return {
            "bb_width": float(width),
            "bb_squeeze": squeeze,
            "bb_breakout": breakout,
            "bb_squeeze_breakout": squeeze and breakout and volume_ok,
        }

