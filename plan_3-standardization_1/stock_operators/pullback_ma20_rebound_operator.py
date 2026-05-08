#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日线回调到MA20后反弹算子
检测近5个交易日是否触及MA20附近并出现反弹确认
"""

import pandas as pd
from typing import Dict, Any
from .base_operator import BaseOperator


class PullbackMA20ReboundOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=80)
        if daily_data.empty or len(daily_data) < 25:
            return {"pullback_ma20_rebound": False}

        daily_data = daily_data.sort_values("date").copy()
        daily_data["ma20"] = daily_data["close"].rolling(20).mean()

        recent = daily_data.tail(6)
        if recent["ma20"].isna().any():
            return {"pullback_ma20_rebound": False}

        tol = 0.01
        touched = False
        for i in range(len(recent) - 1):
            row = recent.iloc[i]
            ma20 = float(row["ma20"])
            if ma20 <= 0:
                continue
            if float(row["low"]) <= ma20 * (1.0 + tol):
                touched = True
                break

        last = daily_data.iloc[-1]
        prev = daily_data.iloc[-2]
        rebound = False
        try:
            rebound = float(last["close"]) > float(last["ma20"]) and float(last["close"]) > float(prev["close"])
        except Exception:
            rebound = False

        return {"pullback_ma20_rebound": touched and rebound}

