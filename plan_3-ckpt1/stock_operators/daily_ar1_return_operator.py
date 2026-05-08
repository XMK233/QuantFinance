#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
日线AR(1)收益模型算子
对对数收益率拟合 AR(1): r_t = c + phi * r_{t-1}
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from .base_operator import BaseOperator


class DailyAR1ReturnOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=160)
        if daily_data.empty or len(daily_data) < 60:
            return {
                "ts_ar1_phi": None,
                "ts_ar1_pred_next": None,
                "ts_ar1_r2": None,
                "ts_ar1_momentum": False,
            }

        daily_data = daily_data.sort_values("date")
        close = pd.to_numeric(daily_data["close"], errors="coerce").astype(float)
        close = close.replace([np.inf, -np.inf], np.nan).dropna()
        if len(close) < 60:
            return {
                "ts_ar1_phi": None,
                "ts_ar1_pred_next": None,
                "ts_ar1_r2": None,
                "ts_ar1_momentum": False,
            }

        r = np.diff(np.log(close.values))
        r = r[np.isfinite(r)]
        if r.size < 50:
            return {
                "ts_ar1_phi": None,
                "ts_ar1_pred_next": None,
                "ts_ar1_r2": None,
                "ts_ar1_momentum": False,
            }

        y = r[1:]
        x1 = r[:-1]
        X = np.column_stack([np.ones_like(x1), x1])
        try:
            beta, _, _, _ = np.linalg.lstsq(X, y, rcond=None)
            c = float(beta[0])
            phi = float(beta[1])
        except Exception:
            return {
                "ts_ar1_phi": None,
                "ts_ar1_pred_next": None,
                "ts_ar1_r2": None,
                "ts_ar1_momentum": False,
            }

        y_hat = X @ np.array([c, phi], dtype=float)
        ss_res = float(np.sum((y - y_hat) ** 2))
        ss_tot = float(np.sum((y - float(np.mean(y))) ** 2))
        r2 = None
        if ss_tot > 0:
            r2 = 1.0 - (ss_res / ss_tot)

        pred_next = c + phi * float(r[-1])
        momentum = bool(phi > 0.1 and pred_next > 0)

        return {
            "ts_ar1_phi": phi,
            "ts_ar1_pred_next": float(pred_next),
            "ts_ar1_r2": float(r2) if r2 is not None else None,
            "ts_ar1_momentum": momentum,
        }

