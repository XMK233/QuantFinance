#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
周线AR(1)收益模型算子
对周对数收益率拟合 AR(1): r_t = c + phi * r_{t-1}
"""

from typing import Dict, Any
import numpy as np
import pandas as pd
from .base_operator import BaseOperator


class WeeklyAR1ReturnOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=120)
        if weekly_data.empty or len(weekly_data) < 60:
            return {
                "ts_w_ar1_phi": None,
                "ts_w_ar1_pred_next": None,
                "ts_w_ar1_momentum": False,
            }

        weekly_data = weekly_data.sort_values("date")
        close = pd.to_numeric(weekly_data["close"], errors="coerce").astype(float)
        close = close.replace([np.inf, -np.inf], np.nan).dropna()
        if len(close) < 60:
            return {
                "ts_w_ar1_phi": None,
                "ts_w_ar1_pred_next": None,
                "ts_w_ar1_momentum": False,
            }

        r = np.diff(np.log(close.values))
        r = r[np.isfinite(r)]
        if r.size < 45:
            return {
                "ts_w_ar1_phi": None,
                "ts_w_ar1_pred_next": None,
                "ts_w_ar1_momentum": False,
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
                "ts_w_ar1_phi": None,
                "ts_w_ar1_pred_next": None,
                "ts_w_ar1_momentum": False,
            }

        pred_next = c + phi * float(r[-1])
        momentum = bool(phi > 0.1 and pred_next > 0)

        return {
            "ts_w_ar1_phi": phi,
            "ts_w_ar1_pred_next": float(pred_next),
            "ts_w_ar1_momentum": momentum,
        }

