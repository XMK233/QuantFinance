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

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(__file__))

from daily_update import update_daily_data
from trading_strategy import TradingStrategy

POSITIONS_FILE = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/positions.csv"
TOTAL_CAPITAL = 50000
FEE_RATE = 0.791 / 10000
MIN_FEE = 5.0

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

def generate_trading_recommendations(exclude_gem=True, exclude_star=True, top_n: int = 20, enable_slow_factors: bool = False, factor_progress: bool = False):
    """
    生成交易推荐
    
    Args:
        exclude_gem: 是否排除创业板股票（默认True）
        exclude_star: 是否排除科创板股票（默认True）
        top_n: 返回前N只推荐股票
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
    
    # 显示推荐结果
    print("📈 今日推荐买入股票:")
    print("=" * 80)
    for idx, row in recommendations.iterrows():
        print(f"{idx+1:2d}. {row['stock_code']:10s} | "
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
    
    for idx, row in recommendations.head(5).iterrows():  # 只显示前5只
        stock_code = row['stock_code']
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
        print(f"{idx+1:2d}. {stock_code:10s} - "
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
    parser.add_argument('--include-gem', action='store_true', help='包含创业板股票（默认排除）')
    parser.add_argument('--max-holdings', type=int, default=3, help='最大持仓数（默认3）')
    parser.add_argument('--ignore-holdings', action='store_true', help='忽略当前持仓数量限制，仍生成买入建议（不写入持仓文件）')
    parser.add_argument('--clear-positions', action='store_true', help='强制清空持仓记录（覆盖 positions.csv）')
    parser.add_argument('--enable-slow-factors', action='store_true', help='启用耗时较长的复杂因子（默认关闭以加快运行）')
    parser.add_argument('--factor-progress', action='store_true', help='打印因子计算进度（会输出当前股票正在计算的因子）')
    args = parser.parse_args()

    global MAX_HOLDINGS
    MAX_HOLDINGS = max(1, int(args.max_holdings))
    
    print(f"🚀 启动每日交易系统 - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 80)
    
    # 更新数据
    if not args.recommend_only:
        update_daily_data()
    
    # 如果只更新数据，则退出
    if args.update_only:
        print("✅ 数据更新完成")
        return

    if args.clear_positions:
        clear_positions()
        print(f"🧹 已清空持仓记录: {POSITIONS_FILE}")

    positions = load_positions()
    sell_df, status_df, positions = generate_sell_recommendations(positions)
    save_positions(positions)

    if status_df is not None and not status_df.empty:
        print("\n📦 当前持仓监控:")
        print("=" * 80)
        for idx, row in status_df.iterrows():
            print(
                f"{idx+1:2d}. {row['stock_code']:10s} | "
                f"现价: {row['current_price']:6.2f} | "
                f"成本: {row['entry_price']:6.2f} | "
                f"收益: {row['profit_pct']:.1%} | "
                f"回撤: {row['drawdown_pct']:.1%}"
            )

    if sell_df is not None and not sell_df.empty:
        print("\n📉 卖出建议:")
        print("=" * 80)
        for idx, row in sell_df.iterrows():
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
        recommendations = generate_trading_recommendations(
            exclude_gem=not args.include_gem,
            exclude_star=True,
            top_n=min(20, available_slots * 5),
            enable_slow_factors=args.enable_slow_factors,
            factor_progress=args.factor_progress,
        )
    
    # 生成具体交易计划
    if recommendations is not None and not recommendations.empty:
        recommendations = recommendations.head(available_slots)
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
