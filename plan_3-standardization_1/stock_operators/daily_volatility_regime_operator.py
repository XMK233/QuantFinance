#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日线波动率状态算子
用快慢EWMA波动率比值刻画波动率抬升/回落的状态
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from .base_operator import BaseOperator


class DailyVolatilityRegimeOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=160)
        if daily_data.empty or len(daily_data) < 80:
            return {
                "ts_vol_ratio": None,
                "ts_vol_high": False,
                "ts_vol_low": False,
            }

        daily_data = daily_data.sort_values("date")
        close = pd.to_numeric(daily_data["close"], errors="coerce").astype(float)
        close = close.replace([np.inf, -np.inf], np.nan).dropna()
        if len(close) < 80:
            return {
                "ts_vol_ratio": None,
                "ts_vol_high": False,
                "ts_vol_low": False,
            }

        r = np.diff(np.log(close.values))
        r = r[np.isfinite(r)]
        if r.size < 60:
            return {
                "ts_vol_ratio": None,
                "ts_vol_high": False,
                "ts_vol_low": False,
            }

        s = pd.Series(r)
        vol_fast = float(s.ewm(span=10, adjust=False).std(bias=True).iloc[-1])
        vol_slow = float(s.ewm(span=40, adjust=False).std(bias=True).iloc[-1])

        ratio = None
        if vol_slow > 0 and np.isfinite(vol_fast) and np.isfinite(vol_slow):
            ratio = vol_fast / vol_slow

        high = bool(ratio is not None and ratio > 1.3)
        low = bool(ratio is not None and ratio < 0.8)

        return {
            "ts_vol_ratio": float(ratio) if ratio is not None else None,
            "ts_vol_high": high,
            "ts_vol_low": low,
        }

