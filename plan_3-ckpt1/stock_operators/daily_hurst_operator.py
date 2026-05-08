#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日线Hurst指数算子
用于刻画序列趋势性(H>0.5)与均值回归(H<0.5)倾向
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from .base_operator import BaseOperator


class DailyHurstOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=220)
        if daily_data.empty or len(daily_data) < 120:
            return {
                "ts_hurst": None,
                "ts_hurst_trend": False,
                "ts_hurst_mean_revert": False,
            }

        daily_data = daily_data.sort_values("date")
        close = pd.to_numeric(daily_data["close"], errors="coerce").astype(float)
        close = close.replace([np.inf, -np.inf], np.nan).dropna()
        if len(close) < 120:
            return {
                "ts_hurst": None,
                "ts_hurst_trend": False,
                "ts_hurst_mean_revert": False,
            }

        logp = np.log(close.values)
        lags = np.array([2, 4, 8, 16, 32], dtype=int)
        taus = []
        valid_lags = []
        for lag in lags:
            if logp.size <= lag + 1:
                continue
            diff = logp[lag:] - logp[:-lag]
            diff = diff[np.isfinite(diff)]
            if diff.size < 10:
                continue
            tau = float(np.sqrt(np.var(diff, ddof=0)))
            if tau <= 0 or not np.isfinite(tau):
                continue
            taus.append(tau)
            valid_lags.append(lag)

        if len(taus) < 3:
            return {
                "ts_hurst": None,
                "ts_hurst_trend": False,
                "ts_hurst_mean_revert": False,
            }

        x = np.log(np.array(valid_lags, dtype=float))
        y = np.log(np.array(taus, dtype=float))
        try:
            slope, _ = np.polyfit(x, y, 1)
            hurst = float(slope)
        except Exception:
            return {
                "ts_hurst": None,
                "ts_hurst_trend": False,
                "ts_hurst_mean_revert": False,
            }

        trend = bool(hurst > 0.55)
        mean_revert = bool(hurst < 0.45)

        return {
            "ts_hurst": hurst,
            "ts_hurst_trend": trend,
            "ts_hurst_mean_revert": mean_revert,
        }

