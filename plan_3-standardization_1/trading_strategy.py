#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
交易策略类
基于多因子组合生成交易信号
"""

import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional

# 导入现有的算子
from stock_operators.cross_ma_operator import CrossMAOperator
from stock_operators.st_operator import STStockOperator, LimitUpOperator
from stock_operators.volume_break_operator import VolumeBreakOperator, MADivergenceOperator
from stock_operators.breakthrough_operator import BreakthroughPullbackOperator, ListingDateOperator
from stock_operators.weekly_breakout_operator import WeeklyBreakoutOperator
from stock_operators.daily_bb_squeeze_operator import DailyBBSqueezeOperator
from stock_operators.pullback_ma20_rebound_operator import PullbackMA20ReboundOperator
from stock_operators.weekly_ma_slope_operator import WeeklyMASlopeOperator
from stock_operators.daily_ar1_return_operator import DailyAR1ReturnOperator
from stock_operators.weekly_ar1_return_operator import WeeklyAR1ReturnOperator
from stock_operators.daily_hurst_operator import DailyHurstOperator
from stock_operators.daily_volatility_regime_operator import DailyVolatilityRegimeOperator
from stock_operators.base_operator import BaseOperator

class TradingStrategy:
    """中长线交易策略"""
    
    def __init__(self, db_path: str = None, enable_slow_factors: bool = False, show_factor_progress: bool = False):
        """初始化策略"""
        self.base_operator = BaseOperator(db_path)
        self.show_factor_progress = bool(show_factor_progress)
        
        # 初始化所有算子
        operators = {
            'cross_ma': CrossMAOperator(db_path),
            'st': STStockOperator(db_path),
            'limit_up': LimitUpOperator(db_path),
            'volume_break': VolumeBreakOperator(db_path),
            'ma_divergence': MADivergenceOperator(db_path),
            'breakthrough': BreakthroughPullbackOperator(db_path),
            'listing_date': ListingDateOperator(db_path),
            'weekly_breakout': WeeklyBreakoutOperator(db_path),
            'pullback_ma20': PullbackMA20ReboundOperator(db_path),
            'weekly_ma_slope': WeeklyMASlopeOperator(db_path),
        }
        if enable_slow_factors:
            operators.update({
                'daily_bb_squeeze': DailyBBSqueezeOperator(db_path),
                'ts_daily_ar1': DailyAR1ReturnOperator(db_path),
                'ts_weekly_ar1': WeeklyAR1ReturnOperator(db_path),
                'ts_hurst': DailyHurstOperator(db_path),
                'ts_vol_regime': DailyVolatilityRegimeOperator(db_path),
            })
        self.operators = operators
        
        # 策略参数
        self.min_listing_days = 240  # 最小上市天数
        self.max_position_size = 0.1  # 单只股票最大仓位
        
    def calculate_all_factors(self, stock_code: str) -> Dict[str, Any]:
        """计算所有因子"""
        factors = {}
        
        # 计算每个算子的因子
        total = len(self.operators)
        for idx, (name, operator) in enumerate(self.operators.items(), start=1):
            try:
                if self.show_factor_progress:
                    print(f"🧮 [{stock_code}] 计算因子 {idx}/{total}: {name}")
                result = operator.calculate(stock_code)
                factors.update(result)
            except Exception as e:
                print(f"计算因子 {name} 出错 ({stock_code}): {e}")
                factors.update({f"{name}_error": True})
        
        return factors
    
    def generate_signal(self, stock_code: str) -> Dict[str, Any]:
        """生成交易信号"""
        # 获取因子数据
        factors = self.calculate_all_factors(stock_code)
        
        # 获取价格数据
        daily_data = self.base_operator.get_daily_data(stock_code, days=20)
        weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=20)
        
        if daily_data.empty or weekly_data.empty:
            return {'signal': 'HOLD', 'confidence': 0, 'reason': '数据不足'}
        
        # 检查数据是否足够计算指标
        if len(daily_data) < 20 or len(weekly_data) < 20:
            return {'signal': 'HOLD', 'confidence': 0, 'reason': '数据不足'}
        
        # 计算技术指标
        current_price = daily_data['close'].iloc[-1]
        
        # 计算移动平均线
        daily_data['ma5'] = daily_data['close'].rolling(5).mean()
        daily_data['ma10'] = daily_data['close'].rolling(10).mean()
        daily_data['ma20'] = daily_data['close'].rolling(20).mean()
        
        weekly_data['ma5'] = weekly_data['close'].rolling(5).mean()
        weekly_data['ma10'] = weekly_data['close'].rolling(10).mean()
        weekly_data['ma20'] = weekly_data['close'].rolling(20).mean()
        
        # 策略逻辑
        buy_signals = []
        sell_signals = []
        buy_score = 0.0
        
        # 买入条件
        # 1. 周线趋势向上
        try:
            weekly_trend_up = weekly_data['ma20'].iloc[-1] > weekly_data['ma20'].iloc[-2]
            if weekly_trend_up:
                buy_signals.append('周线趋势向上')
                buy_score += 0.25
        except (IndexError, KeyError):
            pass  # 数据不足，跳过这个条件
        
        # 2. 日线价格在20日均线之上
        try:
            price_above_ma20 = current_price > daily_data['ma20'].iloc[-1]
            if price_above_ma20:
                buy_signals.append('价格在20日均线之上')
                buy_score += 0.15
        except (IndexError, KeyError):
            pass  # 数据不足，跳过这个条件
        
        # 3. 一阳穿四线信号
        if factors.get('cross_ma_4w', False):
            buy_signals.append('近期有一阳穿四线')
            buy_score += 0.20
        
        # 4. 放量突破
        if factors.get('volume_break_ge_2', False):
            buy_signals.append('放量突破次数达标')
            buy_score += 0.15
        
        # 5. 均线发散
        if factors.get('ma_divergence_bull', factors.get('ma_divergence', False)):
            buy_signals.append('均线多头排列')
            buy_score += 0.15
        
        # 6. 突破回调
        if factors.get('breakthrough_pullback', False):
            buy_signals.append('突破后回调到位')
            buy_score += 0.10

        # 7. 周线20周新高突破（优先使用放量版）
        if factors.get("weekly_breakout_20w_volume", False):
            buy_signals.append("周线突破20周新高(放量)")
            buy_score += 0.20
        elif factors.get("weekly_breakout_20w", False):
            buy_signals.append("周线突破20周新高")
            buy_score += 0.12

        # 8. 日线布林带挤压突破
        if factors.get("bb_squeeze_breakout", False):
            buy_signals.append("日线布林带挤压突破")
            buy_score += 0.15

        # 9. 回调MA20后反弹
        if factors.get("pullback_ma20_rebound", False):
            buy_signals.append("回调MA20后反弹")
            buy_score += 0.10

        # 10. 周线MA20连续上行增强趋势
        if factors.get("weekly_ma20_up_3w", False):
            buy_signals.append("周线MA20连续上行")
            buy_score += 0.08
        
        # 卖出条件
        # 1. ST股票
        if factors.get('is_st', False):
            sell_signals.append('ST股票')
        
        # 2. 上市时间不足
        if not factors.get('listing_gt_240d', True):
            sell_signals.append('上市时间不足')
        
        # 3. 价格跌破20日均线
        price_below_ma20 = current_price < daily_data['ma20'].iloc[-1]
        if price_below_ma20:
            sell_signals.append('价格跌破20日均线')
        
        # 生成最终信号
        if buy_signals and not sell_signals:
            confidence = round(min(buy_score, 1.0), 2)
            return {
                'signal': 'BUY',
                'confidence': confidence,
                'price': current_price,
                'reasons': buy_signals,
                'factors': factors
            }
        elif sell_signals:
            return {
                'signal': 'SELL',
                'confidence': 0.8,
                'price': current_price,
                'reasons': sell_signals,
                'factors': factors
            }
        else:
            return {
                'signal': 'HOLD', 
                'confidence': 0.5,
                'price': current_price,
                'reasons': ['无明显信号'],
                'factors': factors
            }
    
    def generate_daily_recommendations(self, top_n: int = 20, exclude_gem: bool = True, exclude_star: bool = True) -> pd.DataFrame:
        """
        生成每日推荐股票列表
        
        Args:
            top_n: 返回前N只推荐股票
            exclude_gem: 是否排除创业板股票（默认True）
            exclude_star: 是否排除科创板股票（默认True）
        """
        print("📊 生成每日交易推荐...")
        if exclude_gem:
            print("🚫 已启用创业板股票过滤")
        if exclude_star:
            print("🚫 已启用科创板股票过滤")
        
        # 获取所有股票代码（可选择性排除创业板）
        stock_codes = self.base_operator.get_all_stock_codes(exclude_gem=exclude_gem, exclude_star=exclude_star)
        
        recommendations = []
        
        for code in stock_codes:
            try:
                signal = self.generate_signal(code)
                
                if signal['signal'] == 'BUY' and signal['confidence'] >= 0.6:
                    payload = {
                        'stock_code': code,
                        'signal': signal['signal'],
                        'confidence': signal['confidence'],
                        'current_price': signal['price'],
                        'reasons': ' | '.join(signal['reasons'])
                    }
                    factors = signal.get("factors")
                    if isinstance(factors, dict) and factors:
                        payload.update(factors)
                    recommendations.append({
                        **payload
                    })
                    
            except Exception as e:
                print(f"生成信号出错 ({code}): {e}")
                continue
        
        # 按置信度排序
        df = pd.DataFrame(recommendations)
        if not df.empty:
            df = df.sort_values('confidence', ascending=False).head(top_n)
        
        return df

    def _get_latest_daily_price(self, stock_code: str) -> Optional[float]:
        daily_data = self.base_operator.get_daily_data(stock_code, days=5)
        if daily_data.empty:
            return None
        try:
            return float(daily_data['close'].iloc[-1])
        except Exception:
            return None

    def evaluate_take_profit(
        self,
        positions: pd.DataFrame,
        take_profit_pct: float = 0.20,
        trailing_stop_pct: float = 0.08,
        trailing_start_profit_pct: float = 0.10,
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        if positions is None or positions.empty:
            return pd.DataFrame(), positions

        positions = positions.copy()
        for col in ["entry_price", "highest_price", "last_price"]:
            if col in positions.columns:
                positions[col] = pd.to_numeric(positions[col], errors="coerce")

        sell_rows: List[Dict[str, Any]] = []
        today_str = datetime.now().strftime("%Y-%m-%d")

        for idx, row in positions.iterrows():
            stock_code = row.get("stock_code")
            if not isinstance(stock_code, str) or not stock_code:
                continue

            entry_price = row.get("entry_price")
            if entry_price is None or pd.isna(entry_price) or entry_price <= 0:
                continue

            current_price = self._get_latest_daily_price(stock_code)
            if current_price is None or current_price <= 0:
                continue

            positions.at[idx, "last_price"] = current_price
            positions.at[idx, "last_price_date"] = today_str

            highest_price = row.get("highest_price")
            if highest_price is None or pd.isna(highest_price) or highest_price <= 0:
                highest_price = entry_price

            if current_price > highest_price:
                highest_price = current_price
                positions.at[idx, "highest_price"] = highest_price
                positions.at[idx, "highest_price_date"] = today_str

            profit_pct = (current_price / entry_price) - 1.0

            reason = None
            if profit_pct >= take_profit_pct:
                reason = f"固定止盈({take_profit_pct:.0%})"
            else:
                max_profit_pct = (highest_price / entry_price) - 1.0
                drawdown_pct = 1.0 - (current_price / highest_price) if highest_price > 0 else 0.0
                if max_profit_pct >= trailing_start_profit_pct and drawdown_pct >= trailing_stop_pct:
                    reason = f"回撤止盈({trailing_stop_pct:.0%})"

            if reason:
                sell_rows.append(
                    {
                        "stock_code": stock_code,
                        "entry_price": float(entry_price),
                        "current_price": float(current_price),
                        "highest_price": float(highest_price),
                        "profit_pct": float(profit_pct),
                        "reason": reason,
                    }
                )

        sell_df = pd.DataFrame(sell_rows)
        if not sell_df.empty:
            sell_df = sell_df.sort_values(["profit_pct"], ascending=False)

        return sell_df, positions

    def evaluate_positions_for_sell(
        self,
        positions: pd.DataFrame,
        take_profit_pct: float = 0.20,
        trailing_stop_pct: float = 0.08,
        trailing_start_profit_pct: float = 0.10,
        stop_loss_pct: float = 0.08,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        if positions is None or positions.empty:
            empty = pd.DataFrame()
            return empty, empty, positions

        positions = positions.copy()
        for col in ["entry_price", "highest_price", "last_price", "shares"]:
            if col in positions.columns:
                positions[col] = pd.to_numeric(positions[col], errors="coerce")

        today_str = datetime.now().strftime("%Y-%m-%d")
        status_rows: List[Dict[str, Any]] = []

        for idx, row in positions.iterrows():
            stock_code = row.get("stock_code")
            if not isinstance(stock_code, str) or not stock_code:
                continue

            entry_price = row.get("entry_price")
            if entry_price is None or pd.isna(entry_price) or entry_price <= 0:
                continue

            current_price = self._get_latest_daily_price(stock_code)
            if current_price is None or current_price <= 0:
                continue

            positions.at[idx, "last_price"] = current_price
            positions.at[idx, "last_price_date"] = today_str

            highest_price = row.get("highest_price")
            if highest_price is None or pd.isna(highest_price) or highest_price <= 0:
                highest_price = entry_price

            if current_price > highest_price:
                highest_price = current_price
                positions.at[idx, "highest_price"] = highest_price
                positions.at[idx, "highest_price_date"] = today_str

            profit_pct = (current_price / entry_price) - 1.0
            drawdown_pct = 1.0 - (current_price / highest_price) if highest_price > 0 else 0.0
            max_profit_pct = (highest_price / entry_price) - 1.0 if entry_price > 0 else 0.0

            reasons: List[str] = []
            priority = 999

            if stock_code.startswith("sz.30"):
                reasons.append("创业板不在交易范围")
                priority = min(priority, 0)
            if stock_code.startswith("sh.688") or stock_code.startswith("sh.689"):
                reasons.append("科创板不在交易范围")
                priority = min(priority, 0)

            info = self.base_operator.get_stock_info(stock_code)
            name = str(info.get("name", "")) if isinstance(info, dict) else ""
            if "ST" in name:
                reasons.append("ST股票不在交易范围")
                priority = min(priority, 0)

            if profit_pct <= -abs(stop_loss_pct):
                reasons.append(f"止损({abs(stop_loss_pct):.0%})")
                priority = min(priority, 1)

            if profit_pct >= take_profit_pct:
                reasons.append(f"固定止盈({take_profit_pct:.0%})")
                priority = min(priority, 3)
            elif max_profit_pct >= trailing_start_profit_pct and drawdown_pct >= trailing_stop_pct:
                reasons.append(f"回撤止盈({trailing_stop_pct:.0%})")
                priority = min(priority, 2)

            daily_ma20 = None
            try:
                daily_data = self.base_operator.get_daily_data(stock_code, days=25)
                if not daily_data.empty and len(daily_data) >= 20:
                    daily_ma20 = float(daily_data["close"].rolling(20).mean().iloc[-1])
                    if current_price < daily_ma20:
                        reasons.append("跌破20日均线")
                        priority = min(priority, 4)
            except Exception:
                daily_ma20 = None

            weekly_turn_weak = None
            try:
                weekly_data = self.base_operator.get_weekly_data(stock_code, weeks=25)
                if not weekly_data.empty and "ma20" in weekly_data.columns and len(weekly_data) >= 2:
                    weekly_turn_weak = bool(weekly_data["ma20"].iloc[-1] < weekly_data["ma20"].iloc[-2])
                    if weekly_turn_weak:
                        reasons.append("周线MA20转弱")
                        priority = min(priority, 5)
            except Exception:
                weekly_turn_weak = None

            action = "SELL" if reasons else "HOLD"

            status_rows.append(
                {
                    "stock_code": stock_code,
                    "name": name,
                    "entry_price": float(entry_price),
                    "current_price": float(current_price),
                    "highest_price": float(highest_price),
                    "profit_pct": float(profit_pct),
                    "drawdown_pct": float(drawdown_pct),
                    "daily_ma20": daily_ma20,
                    "weekly_turn_weak": weekly_turn_weak,
                    "action": action,
                    "priority": int(priority),
                    "reasons": " | ".join(reasons),
                }
            )

        status_df = pd.DataFrame(status_rows)
        if status_df.empty:
            empty = pd.DataFrame()
            return empty, status_df, positions

        sell_df = status_df[status_df["action"] == "SELL"].copy()
        if not sell_df.empty:
            sell_df = sell_df.sort_values(["priority", "profit_pct"], ascending=[True, True])

        status_df = status_df.sort_values(["action", "profit_pct"], ascending=[True, False])
        return sell_df, status_df, positions

# 示例用法
if __name__ == "__main__":
    strategy = TradingStrategy()
    
    # 测试单个股票
    signal = strategy.generate_signal("sh.600000")
    print(f"测试信号: {signal}")
    
    # 生成推荐列表
    recommendations = strategy.generate_daily_recommendations(10)
    print("\n推荐股票:")
    print(recommendations)
