#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
每日交易系统主程序
自动更新数据并生成交易建议
"""

import argparse
import pandas as pd
from datetime import datetime
import os
import sys

import matplotlib
matplotlib.use("Agg")
from matplotlib import font_manager
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np
from tqdm import tqdm

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from daily_update import update_daily_data
from trading_strategy import TradingStrategy
from stock_operators.base_operator import BaseOperator
from stock_operators.st_operator import STStockOperator
from stock_operators.cross_ma_operator import CrossMAOperator

POSITIONS_FILE = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/positions.csv"
TOTAL_CAPITAL = 50000
FEE_RATE = 0.791 / 10000
MIN_FEE = 5.0

_SIMHEI_TTF = "/mnt/d/forCoding_code/SimHei.ttf"
try:
    if os.path.exists(_SIMHEI_TTF):
        font_manager.fontManager.addfont(_SIMHEI_TTF)
        _simhei_name = font_manager.FontProperties(fname=_SIMHEI_TTF).get_name()
        matplotlib.rcParams["font.family"] = "sans-serif"
        matplotlib.rcParams["font.sans-serif"] = [_simhei_name]
        matplotlib.rcParams["axes.unicode_minus"] = False
except Exception:
    pass

def _get_stock_name(base: BaseOperator, cache: dict, stock_code: str) -> str:
    if not isinstance(stock_code, str) or not stock_code:
        return ""
    hit = cache.get(stock_code)
    if hit is not None:
        return str(hit)
    name = ""
    try:
        info = base.get_stock_info(stock_code)
        if isinstance(info, dict):
            name = str(info.get("name") or "")
    except Exception:
        name = ""
    cache[stock_code] = name
    return name

def load_positions(file_path: str = POSITIONS_FILE) -> pd.DataFrame:
    if not os.path.exists(file_path):
        return pd.DataFrame(columns=[
            "stock_code",
            "entry_date",
            "entry_price",
            "shares",
            "highest_price",
            "highest_price_date",
            "last_price",
            "last_price_date",
        ])
    df = pd.read_csv(file_path)
    if "stock_code" not in df.columns:
        df["stock_code"] = ""
    return df

def save_positions(df: pd.DataFrame, file_path: str = POSITIONS_FILE):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    df.to_csv(file_path, index=False, encoding="utf-8-sig")

def clear_positions(file_path: str = POSITIONS_FILE):
    empty_df = pd.DataFrame(columns=[
        "stock_code",
        "entry_date",
        "entry_price",
        "shares",
        "highest_price",
        "highest_price_date",
        "last_price",
        "last_price_date",
    ])
    save_positions(empty_df, file_path=file_path)

def generate_take_profit_recommendations(positions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    strategy = TradingStrategy()
    sell_df, updated_positions = strategy.evaluate_take_profit(positions)
    return sell_df, updated_positions

def generate_sell_recommendations(positions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    strategy = TradingStrategy()
    sell_df, status_df, updated_positions = strategy.evaluate_positions_for_sell(positions)
    return sell_df, status_df, updated_positions

def calculate_fee(amount: float) -> float:
    if amount <= 0:
        return 0.0
    return max(MIN_FEE, amount * FEE_RATE)

def _plot_kline(df: pd.DataFrame, title: str, output_file: str):
    if df is None or df.empty:
        return

    data = df.copy()
    if "date" not in data.columns:
        return

    data["date"] = pd.to_datetime(data["date"])
    data = data.sort_values("date").dropna(subset=["open", "high", "low", "close"])
    if data.empty:
        return

    for window in (5, 10, 20, 30):
        col = f"ma{window}"
        if col not in data.columns:
            data[col] = data["close"].rolling(window=window).mean()

    dates = mdates.date2num(data["date"].to_numpy(dtype="datetime64[ns]"))
    if len(dates) >= 2:
        diffs = np.diff(dates)
        step = float(np.median(diffs)) if len(diffs) > 0 else 1.0
        candle_width = max(0.2 * step, min(0.8 * step, 0.6 * step))
    else:
        candle_width = 0.6

    fig, (ax1, ax2) = plt.subplots(
        2,
        1,
        figsize=(14, 8),
        sharex=True,
        gridspec_kw={"height_ratios": [3, 1]},
    )

    up = data["close"] >= data["open"]
    down = ~up

    ax1.vlines(dates, data["low"], data["high"], color="black", linewidth=0.6, alpha=0.9)

    def _bar(mask, color: str):
        if not mask.any():
            return
        opens = data.loc[mask, "open"].to_numpy(dtype=float)
        closes = data.loc[mask, "close"].to_numpy(dtype=float)
        bottoms = np.minimum(opens, closes)
        heights = np.abs(closes - opens)
        ax1.bar(
            dates[mask],
            heights,
            bottom=bottoms,
            width=candle_width,
            color=color,
            edgecolor=color,
            alpha=0.8,
            linewidth=0.5,
            align="center",
        )

    _bar(up.to_numpy(), "red")
    _bar(down.to_numpy(), "green")

    for window, color in ((5, "#1f77b4"), (10, "#ff7f0e"), (20, "#9467bd"), (30, "#8c564b")):
        col = f"ma{window}"
        if col in data.columns:
            ax1.plot(dates, data[col], linewidth=1.0, color=color, label=f"MA{window}")

    ax1.set_title(title)
    ax1.grid(True, alpha=0.25)
    ax1.legend(loc="upper left", fontsize=9)

    volumes = data["volume"].fillna(0.0).to_numpy(dtype=float)
    vol_colors = np.where(up.to_numpy(), "red", "green")
    ax2.bar(dates, volumes, width=candle_width, color=vol_colors, alpha=0.6, align="center")
    ax2.grid(True, alpha=0.25)
    ax2.set_ylabel("Volume")

    locator = mdates.AutoDateLocator(minticks=5, maxticks=10)
    formatter = mdates.ConciseDateFormatter(locator)
    ax2.xaxis.set_major_locator(locator)
    ax2.xaxis.set_major_formatter(formatter)

    fig.tight_layout()
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    fig.savefig(output_file, dpi=150, bbox_inches="tight")
    plt.close(fig)

def plot_selected_kline(stock_codes: list[str], output_dir: str, days: int = 180, weeks: int = 180):
    base = BaseOperator()
    for stock_code in stock_codes:
        try:
            info = base.get_stock_info(stock_code)
            name = info.get("name") or ""

            daily = base.get_daily_data(stock_code, days=days)
            weekly = base.get_weekly_data(stock_code, weeks=weeks)

            if daily is not None and not daily.empty:
                daily_file = os.path.join(output_dir, f"{stock_code}_daily.png")
                _plot_kline(daily.tail(120), f"{stock_code} {name} 日K", daily_file)
                print(f"🖼️  已生成日K: {daily_file}")
            else:
                print(f"⚠️  日线数据不足，跳过绘图: {stock_code}")

            if weekly is not None and not weekly.empty:
                weekly_file = os.path.join(output_dir, f"{stock_code}_weekly.png")
                _plot_kline(weekly.tail(120), f"{stock_code} {name} 周K", weekly_file)
                print(f"🖼️  已生成周K: {weekly_file}")
            else:
                print(f"⚠️  周线数据不足，跳过绘图: {stock_code}")
        except Exception as e:
            print(f"⚠️  绘制K线失败 ({stock_code}): {e}")

def generate_trading_recommendations(exclude_gem=True, exclude_star=True, top_n: int = 20, enable_slow_factors: bool = False, factor_progress: bool = False, simple_filter: bool = False):
    """
    生成交易推荐
    
    Args:
        exclude_gem: 是否排除创业板股票（默认True）
        exclude_star: 是否排除科创板股票（默认True）
        top_n: 返回前N只推荐股票
        enable_slow_factors: 启用耗时较长的复杂因子
        factor_progress: 打印因子计算进度
        simple_filter: 仅用简单过滤：非ST、沪深主板、股价<30元、过去3周一阳穿四线
    """
    print("\n🎯 生成交易推荐...")
    print("-" * 50)
    
    # 创建策略实例
    strategy = TradingStrategy(enable_slow_factors=enable_slow_factors, show_factor_progress=factor_progress)
    
    # 生成推荐
    recommendations = strategy.generate_daily_recommendations(top_n=top_n, exclude_gem=exclude_gem, exclude_star=exclude_star)
    if recommendations is not None and not recommendations.empty:
        recommendations = recommendations[~recommendations["stock_code"].astype(str).str.startswith("sh.688")]
        recommendations = recommendations[~recommendations["stock_code"].astype(str).str.startswith("sh.689")]
    
    if recommendations.empty:
        print("⚠️  今日无推荐股票，建议观望")
        return

    base = BaseOperator()
    name_cache: dict = {}
    if "stock_name" not in recommendations.columns:
        recommendations["stock_name"] = recommendations["stock_code"].astype(str).map(lambda x: _get_stock_name(base, name_cache, str(x)))
    
    # 如果启用简单过滤，应用额外条件
    if simple_filter:
        print("🔍 应用简单过滤条件：非ST、沪深主板、股价<30元、过去3周一阳穿四线")
        filtered = []
        for idx, row in recommendations.iterrows():
            stock_code = str(row["stock_code"])
            price = float(row["current_price"])
            factors = row.to_dict()
            
            # 1. 非ST
            if factors.get("is_st", False):
                continue
            
            # 2. 沪深主板（已由 exclude_gem/exclude_star 保证）
            # 3. 股价<30元
            if price >= 30.0:
                continue
            
            # 4. 过去3周一阳穿四线
            if not factors.get("cross_ma_3w", False):
                continue
            
            filtered.append(row)
        
        if not filtered:
            print("⚠️  简单过滤后无符合条件股票")
            return
        
        recommendations = pd.DataFrame(filtered)
        print(f"✅ 简单过滤后剩余 {len(recommendations)} 只股票")
    
    # 显示推荐结果
    print("📈 今日推荐买入股票:")
    print("=" * 80)
    for idx, row in recommendations.iterrows():
        name = str(row.get("stock_name") or "")
        print(f"{idx+1:2d}. {row['stock_code']:10s} | "
              f"名称: {name:6s} | "
              f"价格: {row['current_price']:6.2f} | "
              f"置信度: {row['confidence']:.1%} | "
              f"理由: {row['reasons'][:50]}...")
    
    # 保存推荐结果
    output_dir = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/recommendations/"
    os.makedirs(output_dir, exist_ok=True)
    
    today_str = datetime.now().strftime("%Y%m%d")
    output_file = f"{output_dir}trading_recommendations_{today_str}.csv"
    
    recommendations.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n💾 推荐结果已保存到: {output_file}")
    
    return recommendations

def generate_cross_ma_strategy_recommendations(
    exclude_gem: bool = True,
    exclude_star: bool = True,
    top_n: int = 20,
    price_cap: float = 50.0,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame:
    base = BaseOperator()
    st_op = STStockOperator()
    cross_op = CrossMAOperator()
    name_cache: dict = {}

    if stock_codes is None:
        stock_codes = base.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)
    rows = []
    for code in tqdm(stock_codes, desc="一阳穿四线策略选股", unit="stock"):
        try:
            st = st_op.calculate(code).get("is_st", False)
            if st:
                continue

            cross = cross_op.calculate(code).get("cross_ma_4w", False)
            if not cross:
                continue

            daily = base.get_daily_data(code, days=30)
            if daily is None or daily.empty or len(daily) < 6:
                continue
            current_price = float(daily["close"].iloc[-1])
            if not (current_price > 0):
                continue
            if current_price >= float(price_cap):
                continue
            stock_name = _get_stock_name(base, name_cache, str(code))

            ret_5d = None
            try:
                ret_5d = (current_price / float(daily["close"].iloc[-6])) - 1.0
            except Exception:
                ret_5d = None

            ret_20d = None
            if len(daily) >= 21:
                try:
                    ret_20d = (current_price / float(daily["close"].iloc[-21])) - 1.0
                except Exception:
                    ret_20d = None

            rows.append(
                {
                    "stock_code": str(code),
                    "stock_name": str(stock_name),
                    "signal": "BUY",
                    "confidence": 0.7,
                    "current_price": float(current_price),
                    "reasons": f"一阳穿四线(4周)+非ST+收盘价<{float(price_cap):.0f}",
                    "cross_ma_4w": True,
                    "is_st": False,
                    "ret_5d": float(ret_5d) if ret_5d is not None and pd.notna(ret_5d) else None,
                    "ret_20d": float(ret_20d) if ret_20d is not None and pd.notna(ret_20d) else None,
                }
            )
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    if "ret_20d" in df.columns:
        df = df.sort_values(["ret_20d", "ret_5d"], ascending=False, na_position="last")
    else:
        df = df.sort_values(["ret_5d"], ascending=False, na_position="last")

    df = df.reset_index(drop=True)
    return df.head(int(top_n))

def generate_weekly_mean_down_strategy_recommendations(
    exclude_gem: bool = True,
    exclude_star: bool = True,
    top_n: int = 20,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame:
    base = BaseOperator()
    st_op = STStockOperator()
    name_cache: dict = {}

    if stock_codes is None:
        stock_codes = base.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)

    rows = []
    for code in tqdm(stock_codes, desc="周均价下移策略选股", unit="stock"):
        try:
            st = st_op.calculate(code).get("is_st", False)
            if st:
                continue

            weekly = base.get_weekly_data(code, weeks=70)
            if weekly is None or weekly.empty:
                continue
            weekly = weekly.sort_values("date")
            weekly["close"] = pd.to_numeric(weekly["close"], errors="coerce")
            weekly = weekly.dropna(subset=["close"])
            if len(weekly) < 60:
                continue

            last60 = weekly["close"].tail(60)
            prev30 = last60.iloc[:30]
            recent30 = last60.iloc[30:]
            if prev30.empty or recent30.empty:
                continue
            prev_mean = float(prev30.mean())
            recent_mean = float(recent30.mean())
            if not (prev_mean > 0 and recent_mean > 0):
                continue

            if not (recent_mean < prev_mean):
                continue

            daily = base.get_daily_data(code, days=5)
            if daily is None or daily.empty:
                continue
            current_price = float(pd.to_numeric(daily["close"].iloc[-1], errors="coerce"))
            if not (current_price > 0):
                continue

            stock_name = _get_stock_name(base, name_cache, str(code))
            mean_ratio = recent_mean / prev_mean if prev_mean > 0 else None
            rows.append(
                {
                    "stock_code": str(code),
                    "stock_name": str(stock_name),
                    "signal": "BUY",
                    "confidence": 0.7,
                    "current_price": float(current_price),
                    "reasons": "近0~30周均价 < 近30~60周均价",
                    "weekly_mean_0_30": float(recent_mean),
                    "weekly_mean_30_60": float(prev_mean),
                    "weekly_mean_ratio": float(mean_ratio) if mean_ratio is not None else None,
                }
            )
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values(["weekly_mean_ratio"], ascending=True, na_position="last").reset_index(drop=True)
    return df.head(int(top_n))

def generate_weekly_reg_down_10w_strategy_recommendations(
    exclude_gem: bool = True,
    exclude_star: bool = True,
    top_n: int = 20,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame:
    base = BaseOperator()
    st_op = STStockOperator()
    name_cache: dict = {}

    if stock_codes is None:
        stock_codes = base.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)

    n_weeks = 10
    min_r2 = 0.10

    rows = []
    for code in tqdm(stock_codes, desc="周回归下行(10周)策略选股", unit="stock"):
        try:
            st = st_op.calculate(code).get("is_st", False)
            if st:
                continue

            weekly = base.get_weekly_data(code, weeks=30)
            if weekly is None or weekly.empty:
                continue
            weekly = weekly.sort_values("date")
            close = pd.to_numeric(weekly["close"], errors="coerce").dropna()
            if len(close) < n_weeks:
                continue

            y = close.tail(n_weeks).astype(float).to_numpy()
            if y.size != n_weeks or not np.isfinite(y).all():
                continue

            x = np.arange(n_weeks, dtype=float)
            x_mean = float(x.mean())
            y_mean = float(y.mean())
            denom = float(((x - x_mean) ** 2).sum())
            if denom <= 0:
                continue

            slope = float(((x - x_mean) * (y - y_mean)).sum() / denom)
            intercept = float(y_mean - slope * x_mean)
            y_hat = intercept + slope * x
            ss_res = float(((y - y_hat) ** 2).sum())
            ss_tot = float(((y - y_mean) ** 2).sum())
            r2 = 0.0 if ss_tot <= 0 else float(1.0 - ss_res / ss_tot)

            slope_pct = None
            if y_mean > 0:
                slope_pct = slope / y_mean

            if not (slope < 0):
                continue
            if not (r2 >= min_r2):
                continue

            daily = base.get_daily_data(code, days=5)
            if daily is None or daily.empty:
                continue
            current_price = float(pd.to_numeric(daily["close"].iloc[-1], errors="coerce"))
            if not (current_price > 0):
                continue

            stock_name = _get_stock_name(base, name_cache, str(code))
            rows.append(
                {
                    "stock_code": str(code),
                    "stock_name": str(stock_name),
                    "signal": "BUY",
                    "confidence": 0.7,
                    "current_price": float(current_price),
                    "reasons": "近10周收盘价线性回归后整体呈下降趋势",
                    "weekly_reg_weeks": int(n_weeks),
                    "weekly_reg_slope": float(slope),
                    "weekly_reg_r2": float(r2),
                    "weekly_reg_slope_pct": float(slope_pct) if slope_pct is not None and np.isfinite(slope_pct) else None,
                }
            )
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    sort_cols = ["weekly_reg_slope_pct", "weekly_reg_r2"]
    df = df.sort_values(sort_cols, ascending=[True, False], na_position="last").reset_index(drop=True)
    return df.head(int(top_n))

def generate_bottom_doji_strategy_recommendations(
    exclude_gem: bool = True,
    exclude_star: bool = True,
    top_n: int = 20,
    stock_codes: list[str] | None = None,
) -> pd.DataFrame:
    base = BaseOperator()
    st_op = STStockOperator()
    name_cache: dict = {}

    if stock_codes is None:
        stock_codes = base.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)

    n_weeks = 10
    min_r2 = 0.10
    doji_body_ratio_max = 0.20
    bottom_lookback_weeks = 20
    bottom_close_to_low_max = 1.05

    rows = []
    for code in tqdm(stock_codes, desc="底部十字星策略选股", unit="stock"):
        try:
            st = st_op.calculate(code).get("is_st", False)
            if st:
                continue

            weekly = base.get_weekly_data(code, weeks=80)
            if weekly is None or weekly.empty:
                continue
            weekly = weekly.sort_values("date").copy()
            for col in ["open", "high", "low", "close"]:
                weekly[col] = pd.to_numeric(weekly[col], errors="coerce")
            weekly = weekly.dropna(subset=["open", "high", "low", "close"])
            if len(weekly) < max(60, bottom_lookback_weeks, n_weeks + 2):
                continue

            close_all = weekly["close"].astype(float)
            y = close_all.tail(n_weeks).to_numpy()
            if y.size != n_weeks or not np.isfinite(y).all():
                continue

            x = np.arange(n_weeks, dtype=float)
            x_mean = float(x.mean())
            y_mean = float(y.mean())
            denom = float(((x - x_mean) ** 2).sum())
            if denom <= 0:
                continue

            slope = float(((x - x_mean) * (y - y_mean)).sum() / denom)
            intercept = float(y_mean - slope * x_mean)
            y_hat = intercept + slope * x
            ss_res = float(((y - y_hat) ** 2).sum())
            ss_tot = float(((y - y_mean) ** 2).sum())
            r2 = 0.0 if ss_tot <= 0 else float(1.0 - ss_res / ss_tot)

            slope_pct = None
            if y_mean > 0:
                slope_pct = slope / y_mean

            if not (slope < 0):
                continue
            if not (r2 >= min_r2):
                continue

            w_last2 = weekly.tail(2).copy()
            bottom_hit = False
            best = None
            for offset, wrow in enumerate(w_last2.iloc[::-1].itertuples(index=False), start=0):
                o = float(getattr(wrow, "open"))
                h = float(getattr(wrow, "high"))
                l = float(getattr(wrow, "low"))
                c = float(getattr(wrow, "close"))
                rng = h - l
                if not (rng > 0 and np.isfinite(rng)):
                    continue

                body = abs(c - o)
                body_ratio = body / rng if rng > 0 else None
                is_doji = bool(body_ratio is not None and body_ratio <= doji_body_ratio_max)

                idx = len(weekly) - 1 - offset
                seg = weekly.iloc[max(0, idx - bottom_lookback_weeks + 1) : idx + 1]
                low_min = float(seg["low"].min())
                close_to_low = None
                if low_min > 0:
                    close_to_low = c / low_min
                is_bottom = bool(close_to_low is not None and close_to_low <= bottom_close_to_low_max)

                if is_doji and is_bottom:
                    bottom_hit = True
                    best = {
                        "doji_week_offset": int(offset),
                        "doji_body_ratio": float(body_ratio) if body_ratio is not None else None,
                        "bottom_close_to_low": float(close_to_low) if close_to_low is not None else None,
                    }
                    break

            if not bottom_hit or best is None:
                continue

            daily = base.get_daily_data(code, days=5)
            if daily is None or daily.empty:
                continue
            current_price = float(pd.to_numeric(daily["close"].iloc[-1], errors="coerce"))
            if not (current_price > 0):
                continue

            stock_name = _get_stock_name(base, name_cache, str(code))
            rows.append(
                {
                    "stock_code": str(code),
                    "stock_name": str(stock_name),
                    "signal": "BUY",
                    "confidence": 0.7,
                    "current_price": float(current_price),
                    "reasons": "先满足近10周回归下行，再满足近2周出现底部十字星",
                    "weekly_reg_weeks": int(n_weeks),
                    "weekly_reg_slope": float(slope),
                    "weekly_reg_r2": float(r2),
                    "weekly_reg_slope_pct": float(slope_pct) if slope_pct is not None and np.isfinite(slope_pct) else None,
                    "doji_week_offset": int(best["doji_week_offset"]),
                    "doji_body_ratio": float(best["doji_body_ratio"]) if best.get("doji_body_ratio") is not None else None,
                    "bottom_close_to_low": float(best["bottom_close_to_low"]) if best.get("bottom_close_to_low") is not None else None,
                }
            )
        except Exception:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return df

    df = df.sort_values(
        ["bottom_close_to_low", "doji_week_offset", "weekly_reg_slope_pct", "weekly_reg_r2"],
        ascending=[True, True, True, False],
        na_position="last",
    ).reset_index(drop=True)
    return df.head(int(top_n))

def generate_chained_strategy_recommendations(
    strategies: list[str],
    exclude_gem: bool = True,
    exclude_star: bool = True,
    price_cap: float = 50.0,
    final_top_n: int = 3,
) -> pd.DataFrame:
    base = BaseOperator()
    stock_codes = base.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)
    current_df: pd.DataFrame | None = None

    for s in strategies:
        s = str(s).strip()
        if not s:
            continue

        if current_df is None:
            input_codes = stock_codes
        else:
            input_codes = [str(x) for x in current_df["stock_code"].astype(str).tolist()]

        if s == "cross_ma50":
            step_df = generate_cross_ma_strategy_recommendations(
                exclude_gem=exclude_gem,
                exclude_star=exclude_star,
                top_n=max(200, final_top_n * 50),
                price_cap=float(price_cap),
                stock_codes=input_codes,
            )
        elif s == "weekly_mean_down":
            step_df = generate_weekly_mean_down_strategy_recommendations(
                exclude_gem=exclude_gem,
                exclude_star=exclude_star,
                top_n=max(500, final_top_n * 80),
                stock_codes=input_codes,
            )
        elif s == "weekly_reg_down_10w":
            step_df = generate_weekly_reg_down_10w_strategy_recommendations(
                exclude_gem=exclude_gem,
                exclude_star=exclude_star,
                top_n=max(500, final_top_n * 80),
                stock_codes=input_codes,
            )
        elif s == "bottom_doji":
            step_df = generate_bottom_doji_strategy_recommendations(
                exclude_gem=exclude_gem,
                exclude_star=exclude_star,
                top_n=max(500, final_top_n * 80),
                stock_codes=input_codes,
            )
        else:
            raise ValueError(f"未知策略: {s}")

        if step_df is None or step_df.empty:
            return pd.DataFrame()

        step_df = step_df.copy()
        step_df = step_df.drop_duplicates(subset=["stock_code"], keep="first")
        step_df["reasons"] = step_df["reasons"].astype(str).map(lambda x: f"[{s}] {x}")

        if current_df is None:
            current_df = step_df
        else:
            current_df = current_df.drop_duplicates(subset=["stock_code"], keep="first").copy()
            step_df = step_df.rename(columns={"reasons": "reasons_step"})

            new_cols = [c for c in step_df.columns if c not in ("stock_code", "reasons_step") and c not in current_df.columns]
            merged = current_df.merge(step_df[["stock_code", "reasons_step", *new_cols]], on="stock_code", how="inner")
            merged["reasons"] = merged["reasons"].astype(str) + " | " + merged["reasons_step"].astype(str)
            merged = merged.drop(columns=["reasons_step"])
            current_df = merged

    if current_df is None or current_df.empty:
        return pd.DataFrame()

    if "ret_20d" in current_df.columns:
        current_df = current_df.sort_values(["ret_20d", "ret_5d"], ascending=False, na_position="last")
    elif "weekly_reg_slope_pct" in current_df.columns:
        current_df = current_df.sort_values(["weekly_reg_slope_pct", "weekly_reg_r2"], ascending=[True, False], na_position="last")
    elif "weekly_mean_ratio" in current_df.columns:
        current_df = current_df.sort_values(["weekly_mean_ratio"], ascending=True, na_position="last")
    else:
        current_df = current_df

    current_df = current_df.reset_index(drop=True)
    return current_df.head(int(final_top_n))

def generate_trading_plan(recommendations, persist_positions: bool = True):
    """生成具体的交易计划"""
    if recommendations.empty:
        return
    
    print("\n📋 具体交易计划:")
    print("=" * 80)
    
    total_capital = TOTAL_CAPITAL
    
    print(f"💰 总资金: {total_capital:,} 元")
    print(f"📊 最大持仓数: {MAX_HOLDINGS} 只")
    target_position_value = total_capital / MAX_HOLDINGS
    print(f"📊 单只股票目标资金: {target_position_value:,.0f} 元")
    print("\n🎯 建议操作:")
    
    base = BaseOperator()
    name_cache: dict = {}
    for idx, row in recommendations.head(5).iterrows():  # 只显示前5只
        stock_code = row['stock_code']
        stock_name = str(row.get("stock_name") or _get_stock_name(base, name_cache, str(stock_code)))
        price = row['current_price']
        confidence = row['confidence']
        
        target_amount = target_position_value
        shares = int(target_amount / price / 100) * 100
        for _ in range(2):
            amount = shares * price
            fee = calculate_fee(amount)
            shares = int(max(0.0, target_amount - fee) / price / 100) * 100
        
        amount = shares * price
        fee = calculate_fee(amount)
        print(f"{idx+1:2d}. {stock_code:10s} {stock_name:6s} - "
              f"建议买入: {shares:,} 股 | "
              f"价格: {price:6.2f}元 | "
              f"投入: {amount:,.0f}元 | "
              f"手续费: {fee:,.2f}元 | "
              f"置信度: {confidence:.1%}")

    if not persist_positions:
        return

    positions = load_positions()
    existing = set(str(x) for x in positions["stock_code"].astype(str).tolist())
    today_str = datetime.now().strftime("%Y-%m-%d")
    new_rows = []
    for _, row in recommendations.head(MAX_HOLDINGS).iterrows():
        stock_code = str(row["stock_code"])
        if stock_code in existing:
            continue
        price = float(row["current_price"])
        target_amount = target_position_value
        shares = int(target_amount / price / 100) * 100
        for _ in range(2):
            amount = shares * price
            fee = calculate_fee(amount)
            shares = int(max(0.0, target_amount - fee) / price / 100) * 100
        if shares <= 0:
            continue
        new_rows.append({
            "stock_code": stock_code,
            "entry_date": today_str,
            "entry_price": price,
            "shares": shares,
            "highest_price": price,
            "highest_price_date": today_str,
            "last_price": price,
            "last_price_date": today_str,
        })
    if new_rows:
        positions = pd.concat([positions, pd.DataFrame(new_rows)], ignore_index=True)
        save_positions(positions)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(description='每日交易系统')
    parser.add_argument('--update-only', action='store_true', help='只更新数据，不生成推荐')
    parser.add_argument('--recommend-only', action='store_true', help='只生成推荐，不更新数据')
    parser.add_argument('--skip-update', action='store_true', help='跳过数据更新步骤，直接使用现有数据库数据进入后续流程')
    parser.add_argument('--strategy', nargs='+', default=['multi_factor'], help='选股策略，可传多个按顺序依次筛选：multi_factor / cross_ma50 / weekly_mean_down / weekly_reg_down_10w / bottom_doji')
    parser.add_argument('--price-cap', type=float, default=50.0, help='价格上限（用于 cross_ma50 策略，默认50）')
    parser.add_argument('--include-gem', action='store_true', help='包含创业板股票（默认排除）')
    parser.add_argument('--max-holdings', type=int, default=3, help='最大持仓数（默认3）')
    parser.add_argument('--ignore-holdings', action='store_true', help='忽略当前持仓数量限制，仍生成买入建议（不写入持仓文件）')
    parser.add_argument('--clear-positions', action='store_true', help='强制清空持仓记录（覆盖 positions.csv）')
    parser.add_argument('--enable-slow-factors', action='store_true', help='启用耗时较长的复杂因子（默认关闭以加快运行）')
    parser.add_argument('--factor-progress', action='store_true', help='打印因子计算进度（会输出当前股票正在计算的因子）')
    parser.add_argument('--simple-filter', action='store_true', help='仅用简单过滤：非ST、沪深主板、股价<30元、过去3周一阳穿四线')
    args = parser.parse_args()

    global MAX_HOLDINGS
    MAX_HOLDINGS = max(1, int(args.max_holdings))
    
    print(f"🚀 启动每日交易系统 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    # 更新数据
    if not args.recommend_only and not args.skip_update:
        update_daily_data()
    elif args.skip_update and not args.recommend_only:
        print("⏭️ 已跳过数据更新（--skip-update），使用现有数据库数据")
    
    # 如果只更新数据，则退出
    if args.update_only:
        if args.skip_update:
            print("✅ 已跳过数据更新")
        else:
            print("✅ 数据更新完成")
        return

    if args.clear_positions:
        clear_positions()
        print(f"🧹 已清空持仓记录: {POSITIONS_FILE}")

    base = BaseOperator()
    name_cache: dict = {}
    positions = load_positions()
    sell_df, status_df, positions = generate_sell_recommendations(positions)
    save_positions(positions)

    if status_df is not None and not status_df.empty:
        print("\n📦 当前持仓监控:")
        print("=" * 80)
        for idx, row in status_df.iterrows():
            name = _get_stock_name(base, name_cache, str(row.get("stock_code")))
            print(
                f"{idx+1:2d}. {row['stock_code']:10s} | "
                f"名称: {name:6s} | "
                f"现价: {row['current_price']:6.2f} | "
                f"成本: {row['entry_price']:6.2f} | "
                f"收益: {row['profit_pct']:.1%} | "
                f"回撤: {row['drawdown_pct']:.1%}"
            )

    if sell_df is not None and not sell_df.empty:
        print("\n📉 卖出建议:")
        print("=" * 80)
        for idx, row in sell_df.iterrows():
            name = _get_stock_name(base, name_cache, str(row.get("stock_code")))
            shares = 0
            try:
                p_row = positions[positions["stock_code"].astype(str) == str(row["stock_code"])].tail(1)
                if not p_row.empty and "shares" in p_row.columns:
                    shares = int(float(p_row["shares"].iloc[0]))
            except Exception:
                shares = 0

            amount = (shares * float(row["current_price"])) if shares > 0 else 0.0
            fee = calculate_fee(amount) if amount > 0 else 0.0

            print(
                f"{idx+1:2d}. {row['stock_code']:10s} | "
                f"名称: {name:6s} | "
                f"现价: {row['current_price']:6.2f} | "
                f"成本: {row['entry_price']:6.2f} | "
                f"收益: {row['profit_pct']:.1%} | "
                f"原因: {row['reasons']} | "
                f"预估手续费: {fee:,.2f}"
            )
    
    current_holdings = int(positions["stock_code"].astype(str).str.len().gt(0).sum()) if not positions.empty else 0
    if args.ignore_holdings:
        available_slots = MAX_HOLDINGS
    else:
        available_slots = max(0, MAX_HOLDINGS - current_holdings)

    if available_slots <= 0 and not args.ignore_holdings:
        print(f"\n🧱 持仓已满: {current_holdings}/{MAX_HOLDINGS}，本次不再给出新的买入建议")
        recommendations = None
    else:
        strategies = [str(x).strip() for x in (args.strategy or []) if str(x).strip()]
        if len(strategies) == 1 and strategies[0] == "multi_factor":
            recommendations = generate_trading_recommendations(
                exclude_gem=not args.include_gem,
                exclude_star=True,
                top_n=min(20, available_slots * 5),
                enable_slow_factors=args.enable_slow_factors,
                factor_progress=args.factor_progress,
                simple_filter=args.simple_filter,
            )
        else:
            if "multi_factor" in strategies:
                raise ValueError("multi_factor 暂不支持与其他策略链式组合，请单独使用或只传简单策略。")
            final_n = 3 if args.ignore_holdings else min(3, available_slots)
            recommendations = generate_chained_strategy_recommendations(
                strategies=strategies,
                exclude_gem=not args.include_gem,
                exclude_star=True,
                price_cap=float(args.price_cap),
                final_top_n=int(final_n),
            )
            if recommendations is not None and not recommendations.empty:
                output_dir = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/recommendations/"
                os.makedirs(output_dir, exist_ok=True)
                today_str = datetime.now().strftime("%Y%m%d")
                tag = "_".join(strategies)
                output_file = f"{output_dir}strategy_chain_{tag}_{today_str}.csv"
                recommendations.to_csv(output_file, index=False, encoding="utf-8-sig")
                print(f"\n💾 策略结果已保存到: {output_file}")
    
    # 生成具体交易计划
    if recommendations is not None and not recommendations.empty:
        final_n = 3 if args.ignore_holdings else min(3, available_slots)
        recommendations = recommendations.head(final_n)
        today_str = datetime.now().strftime("%Y%m%d")
        chart_dir = os.path.join(os.path.dirname(__file__), f"kline_charts_{today_str}")
        print(f"\n🖼️  绘制入股候选的日K/周K（共 {len(recommendations)} 只）...")
        plot_selected_kline([str(x) for x in recommendations["stock_code"].astype(str).tolist()], chart_dir)
        generate_trading_plan(recommendations, persist_positions=not args.ignore_holdings)
    
    print("\n" + "=" * 80)
    print("✅ 每日交易系统执行完成")
    print(f"⏰ 完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

# 定时任务配置示例
if __name__ == "__main__":
    """
    使用说明:
    1. 每日收盘后运行: python daily_trading_system.py
    2. 只更新数据: python daily_trading_system.py --update-only
    3. 只生成推荐: python daily_trading_system.py --recommend-only
    
    建议设置定时任务:
    # 每天收盘后15:30执行
    30 15 * * 1-5 cd /mnt/d/forCoding_code/QuantFinance/plan_3-standardization_1 && python daily_trading_system.py
    """
    
    main()
