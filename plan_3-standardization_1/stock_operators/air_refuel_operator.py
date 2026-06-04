#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
空中加油形态算子
提供三类因子：A(规则型)、B(连续打分型)、C(多周期共振)
"""

from typing import Dict, Any, Optional, Tuple
import pandas as pd
from .base_operator import BaseOperator


def _clip01(x: float) -> float:
    try:
        if x < 0:
            return 0.0
        if x > 1:
            return 1.0
        return float(x)
    except Exception:
        return 0.0


def _score_linear(x: Optional[float], x0: float, x1: float, higher_better: bool = True) -> float:
    if x is None or not pd.notna(x):
        return 0.0
    try:
        xv = float(x)
    except Exception:
        return 0.0
    if x1 == x0:
        return 0.0
    if higher_better:
        return _clip01((xv - x0) / (x1 - x0))
    return _clip01((x1 - xv) / (x1 - x0))


def _prep_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    df = df.sort_values("date").copy()
    for col in ["open", "high", "low", "close", "volume", "amount"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df.dropna(subset=["high", "low", "close", "volume"])
    return df


def _compute_rel_range(df: pd.DataFrame) -> pd.Series:
    close = df["close"]
    rr = (df["high"] - df["low"]) / close.replace(0, pd.NA)
    return rr


def _split_pole_flag(df: pd.DataFrame, pole_days: int, flag_days: int) -> Optional[Tuple[pd.DataFrame, pd.DataFrame]]:
    if df is None or df.empty:
        return None
    need = pole_days + flag_days
    if len(df) < need:
        return None
    flag_df = df.tail(flag_days)
    pole_df = df.iloc[-need:-flag_days]
    if len(flag_df) != flag_days or len(pole_df) != pole_days:
        return None
    return pole_df, flag_df


def _extract_air_refuel_parts_daily(df: pd.DataFrame, pole_days: int, flag_days: int) -> Optional[Dict[str, Any]]:
    parts = _split_pole_flag(df, pole_days=pole_days, flag_days=flag_days)
    if parts is None:
        return None
    pole_df, flag_df = parts

    pole_high = float(pole_df["high"].max())
    pole_low = float(pole_df["low"].min())
    pole_start = float(pole_df["close"].iloc[0])
    pole_end = float(pole_df["close"].iloc[-1])
    if pole_start <= 0 or pole_high <= 0:
        return None
    pole_return = (pole_end / pole_start) - 1.0

    flag_low = float(flag_df["low"].min())
    flag_high = float(flag_df["high"].max())
    last_close = float(flag_df["close"].iloc[-1])
    last_volume = float(flag_df["volume"].iloc[-1])

    flag_high_prev = None
    if len(flag_df) >= 2:
        flag_high_prev = float(flag_df["high"].iloc[:-1].max())
    if flag_high_prev is None or flag_high_prev <= 0:
        flag_high_prev = float(flag_df["high"].max())

    pullback_depth = (flag_low / pole_high) - 1.0
    retrace_ratio = None
    denom = pole_high - pole_low
    if denom > 0:
        retrace_ratio = (pole_high - flag_low) / denom

    flag_range = None
    if last_close > 0:
        flag_range = (flag_high - flag_low) / last_close

    pole_vol_mean = float(pole_df["volume"].mean()) if pole_df["volume"].mean() > 0 else None
    flag_vol_mean = float(flag_df["volume"].mean()) if flag_df["volume"].mean() > 0 else None
    vol_ratio = None
    if pole_vol_mean is not None and flag_vol_mean is not None and pole_vol_mean > 0:
        vol_ratio = flag_vol_mean / pole_vol_mean

    rr = _compute_rel_range(df)
    pole_rr = float(rr.iloc[-(pole_days + flag_days):-flag_days].mean())
    flag_rr = float(rr.iloc[-flag_days:].mean())
    rr_ratio = None
    if pole_rr > 0 and pd.notna(pole_rr) and pd.notna(flag_rr):
        rr_ratio = flag_rr / pole_rr

    breakout = bool(last_close > flag_high_prev) if flag_high_prev > 0 else False
    breakout_vol = bool(flag_vol_mean is not None and flag_vol_mean > 0 and last_volume > flag_vol_mean * 1.5)

    return {
        "pole_return": float(pole_return),
        "pullback_depth": float(pullback_depth),
        "retrace_ratio": float(retrace_ratio) if retrace_ratio is not None and pd.notna(retrace_ratio) else None,
        "flag_range": float(flag_range) if flag_range is not None and pd.notna(flag_range) else None,
        "rr_ratio": float(rr_ratio) if rr_ratio is not None and pd.notna(rr_ratio) else None,
        "vol_ratio": float(vol_ratio) if vol_ratio is not None and pd.notna(vol_ratio) else None,
        "breakout": breakout,
        "breakout_vol": breakout_vol,
        "flag_high_prev": float(flag_high_prev),
        "last_close": float(last_close),
        "last_volume": float(last_volume),
        "flag_vol_mean": float(flag_vol_mean) if flag_vol_mean is not None and pd.notna(flag_vol_mean) else None,
    }


class AirRefuelRuleOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=140)
        if daily_data.empty or len(daily_data) < 90:
            return {"air_refuel_rule": False}

        daily_data = _prep_ohlcv(daily_data)
        if len(daily_data) < 90:
            return {"air_refuel_rule": False}

        daily_data["ma20"] = daily_data["close"].rolling(20).mean()
        daily_data["ma60"] = daily_data["close"].rolling(60).mean()
        last = daily_data.iloc[-1]

        trend_ok = False
        try:
            close = float(last["close"])
            ma20 = float(last["ma20"])
            ma60 = float(last["ma60"])
            ma20_prev = float(daily_data["ma20"].iloc[-6])
            trend_ok = (close > ma20 > ma60) and (ma20_prev > 0) and (ma20 > ma20_prev)
        except Exception:
            trend_ok = False

        info = _extract_air_refuel_parts_daily(daily_data, pole_days=15, flag_days=10)
        if info is None:
            return {"air_refuel_rule": False}

        pole_ok = bool(info["pole_return"] >= 0.12)
        pullback_ok = bool(info["pullback_depth"] >= -0.08)
        retrace_ok = bool(info["retrace_ratio"] is None or float(info["retrace_ratio"]) <= 0.55)
        tight_ok = bool(info["flag_range"] is not None and float(info["flag_range"]) <= 0.12)
        vol_comp_ok = bool(info["rr_ratio"] is not None and float(info["rr_ratio"]) <= 0.85)
        dryup_ok = bool(info["vol_ratio"] is not None and float(info["vol_ratio"]) <= 0.85)

        signal = bool(
            pole_ok
            and trend_ok
            and pullback_ok
            and retrace_ok
            and tight_ok
            and vol_comp_ok
            and dryup_ok
            and bool(info["breakout"])
            and bool(info["breakout_vol"])
        )

        return {"air_refuel_rule": signal}


class AirRefuelScoreOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=140)
        if daily_data.empty or len(daily_data) < 90:
            return {"air_refuel_score": None}

        daily_data = _prep_ohlcv(daily_data)
        if len(daily_data) < 90:
            return {"air_refuel_score": None}

        daily_data["ma20"] = daily_data["close"].rolling(20).mean()
        daily_data["ma60"] = daily_data["close"].rolling(60).mean()
        last = daily_data.iloc[-1]

        trend_score = 0.0
        try:
            close = float(last["close"])
            ma20 = float(last["ma20"])
            ma60 = float(last["ma60"])
            ma20_prev = float(daily_data["ma20"].iloc[-6])
            order = 1.0 if (close > ma20 > ma60) else 0.0
            slope = None
            if ma20_prev > 0:
                slope = (ma20 / ma20_prev) - 1.0
            trend_score = 0.7 * order + 0.3 * _score_linear(slope, 0.0, 0.03, higher_better=True)
        except Exception:
            trend_score = 0.0

        info = _extract_air_refuel_parts_daily(daily_data, pole_days=15, flag_days=10)
        if info is None:
            return {"air_refuel_score": None}

        momentum = _score_linear(info.get("pole_return"), 0.08, 0.28, higher_better=True)
        abs_depth = None
        try:
            abs_depth = max(0.0, -float(info["pullback_depth"]))
        except Exception:
            abs_depth = None
        depth_score = _score_linear(abs_depth, 0.10, 0.00, higher_better=False)
        retrace_score = _score_linear(info.get("retrace_ratio"), 0.60, 0.25, higher_better=False)
        tight_score = _score_linear(info.get("flag_range"), 0.15, 0.06, higher_better=False)
        vol_comp = _score_linear(info.get("rr_ratio"), 1.00, 0.60, higher_better=False)
        vol_dry = _score_linear(info.get("vol_ratio"), 1.00, 0.60, higher_better=False)

        breakout_strength = 0.0
        try:
            if bool(info["breakout"]) and float(info["flag_high_prev"]) > 0:
                gain = (float(info["last_close"]) / float(info["flag_high_prev"])) - 1.0
                breakout_strength = _score_linear(gain, 0.00, 0.05, higher_better=True)
        except Exception:
            breakout_strength = 0.0

        breakout_volume = 0.0
        try:
            if bool(info["breakout_vol"]) and info.get("flag_vol_mean") is not None and float(info["flag_vol_mean"]) > 0:
                vr = float(info["last_volume"]) / float(info["flag_vol_mean"])
                breakout_volume = _score_linear(vr, 1.2, 2.5, higher_better=True)
        except Exception:
            breakout_volume = 0.0

        breakout_score = 0.6 * breakout_strength + 0.4 * breakout_volume

        score = (
            0.22 * momentum
            + 0.18 * trend_score
            + 0.12 * depth_score
            + 0.10 * retrace_score
            + 0.12 * tight_score
            + 0.10 * vol_comp
            + 0.08 * vol_dry
            + 0.08 * breakout_score
        )

        return {"air_refuel_score": float(_clip01(score))}


class AirRefuelMultiTimeframeOperator:
    def __init__(self, db_path: str = None):
        self.base_operator = BaseOperator(db_path)

    def calculate(self, stock_code: str) -> Dict[str, Any]:
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=90)
        if weekly_data.empty or len(weekly_data) < 40:
            return {"air_refuel_mt_score": None}

        weekly_data = _prep_ohlcv(weekly_data)
        if len(weekly_data) < 40:
            return {"air_refuel_mt_score": None}

        weekly_data["ma20"] = weekly_data["close"].rolling(20).mean()
        last_w = weekly_data.iloc[-1]

        trend_w = 0.0
        try:
            close_w = float(last_w["close"])
            ma20_w = float(last_w["ma20"])
            ma20_prev_w = float(weekly_data["ma20"].iloc[-4])
            order_w = 1.0 if (ma20_w > 0 and close_w > ma20_w) else 0.0
            slope_w = None
            if ma20_prev_w > 0:
                slope_w = (ma20_w / ma20_prev_w) - 1.0
            trend_w = 0.7 * order_w + 0.3 * _score_linear(slope_w, 0.0, 0.04, higher_better=True)
        except Exception:
            trend_w = 0.0

        parts_w = _split_pole_flag(weekly_data, pole_days=8, flag_days=4)
        if parts_w is None:
            return {"air_refuel_mt_score": None}
        pole_w, flag_w = parts_w

        pole_high = float(pole_w["high"].max())
        pole_low = float(pole_w["low"].min())
        pole_start = float(pole_w["close"].iloc[0])
        pole_end = float(pole_w["close"].iloc[-1])
        if pole_start <= 0 or pole_high <= 0:
            return {"air_refuel_mt_score": None}

        pole_ret_w = (pole_end / pole_start) - 1.0
        flag_low_w = float(flag_w["low"].min())
        flag_high_w = float(flag_w["high"].max())
        last_close_w = float(flag_w["close"].iloc[-1])

        retrace_ratio_w = None
        denom = pole_high - pole_low
        if denom > 0:
            retrace_ratio_w = (pole_high - flag_low_w) / denom

        flag_range_w = None
        if last_close_w > 0:
            flag_range_w = (flag_high_w - flag_low_w) / last_close_w

        rrw = _compute_rel_range(weekly_data)
        pole_rr_w = float(rrw.iloc[-(8 + 4):-4].mean())
        flag_rr_w = float(rrw.iloc[-4:].mean())
        rr_ratio_w = None
        if pole_rr_w > 0 and pd.notna(pole_rr_w) and pd.notna(flag_rr_w):
            rr_ratio_w = flag_rr_w / pole_rr_w

        pole_vol_w = float(pole_w["volume"].mean()) if pole_w["volume"].mean() > 0 else None
        flag_vol_w = float(flag_w["volume"].mean()) if flag_w["volume"].mean() > 0 else None
        vol_ratio_w = None
        if pole_vol_w is not None and flag_vol_w is not None and pole_vol_w > 0:
            vol_ratio_w = flag_vol_w / pole_vol_w

        momentum_w = _score_linear(pole_ret_w, 0.12, 0.35, higher_better=True)
        retrace_w = _score_linear(retrace_ratio_w, 0.65, 0.25, higher_better=False)
        tight_w = _score_linear(flag_range_w, 0.18, 0.08, higher_better=False)
        vol_comp_w = _score_linear(rr_ratio_w, 1.00, 0.65, higher_better=False)
        vol_dry_w = _score_linear(vol_ratio_w, 1.00, 0.65, higher_better=False)

        weekly_score = _clip01(
            0.30 * momentum_w
            + 0.20 * trend_w
            + 0.18 * retrace_w
            + 0.16 * tight_w
            + 0.08 * vol_comp_w
            + 0.08 * vol_dry_w
        )

        daily_data = self.base_operator.get_daily_data(stock_code, days=80)
        if daily_data.empty or len(daily_data) < 35:
            return {"air_refuel_mt_score": float(weekly_score)}

        daily_data = _prep_ohlcv(daily_data)
        if len(daily_data) < 35:
            return {"air_refuel_mt_score": float(weekly_score)}

        daily_data["volume_ma20"] = daily_data["volume"].rolling(20).mean()
        recent = daily_data.tail(12)
        daily_breakout = 0.0
        try:
            last_d = recent.iloc[-1]
            prev_high = float(recent["high"].iloc[:-1].max())
            close_d = float(last_d["close"])
            vma20 = float(daily_data["volume_ma20"].iloc[-1])
            vol_d = float(last_d["volume"])
            price_ok = close_d > prev_high if prev_high > 0 else False
            vol_ok = (vma20 > 0) and (vol_d > vma20 * 1.2)
            if price_ok:
                gain = (close_d / prev_high) - 1.0
                daily_breakout = 0.7 * _score_linear(gain, 0.00, 0.04, higher_better=True) + 0.3 * (1.0 if vol_ok else 0.0)
            else:
                daily_breakout = 0.0
        except Exception:
            daily_breakout = 0.0

        mt_score = _clip01(0.65 * weekly_score + 0.35 * daily_breakout)
        return {"air_refuel_mt_score": float(mt_score)}

