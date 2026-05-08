#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周线MA20斜率算子
给出MA20近几周的斜率与连续上行判断
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class WeeklyMASlopeOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=30)
        if weekly_data.empty or len(weekly_data) < 22:
            return {
                "weekly_ma20_slope": None,
                "weekly_ma20_up_3w": False,
            }

        weekly_data = weekly_data.sort_values("date").copy()
        weekly_data["ma20"] = weekly_data["close"].rolling(20).mean()
        last3 = weekly_data.tail(3)
        if last3["ma20"].isna().any():
            return {
                "weekly_ma20_slope": None,
                "weekly_ma20_up_3w": False,
            }

        ma_prev = float(last3["ma20"].iloc[-2])
        ma_last = float(last3["ma20"].iloc[-1])
        slope = None
        if ma_prev > 0:
            slope = (ma_last / ma_prev) - 1.0

        up_3w = bool(
            float(last3["ma20"].iloc[-1]) > float(last3["ma20"].iloc[-2]) > float(last3["ma20"].iloc[-3])
        )

        return {
            "weekly_ma20_slope": float(slope) if slope is not None else None,
            "weekly_ma20_up_3w": up_3w,
        }

