#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
结果导出器
专门处理回测结果的输出和保存
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
import json
import matplotlib.pyplot as plt
import matplotlib
from matplotlib import font_manager
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
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

class ResultsExporter:
    """结果导出器"""
    
    def __init__(self, output_dir="backtest_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def export_daily_records(self, daily_df, prefix="daily"):
        """
        导出每日记录
        
        Args:
            daily_df: 每日记录DataFrame
            prefix: 文件前缀
            
        Returns:
            保存的文件路径
        """
        if daily_df.empty:
            print("⚠️  无每日记录数据可导出")
            return None
        
        # 确保日期列是datetime类型
        if 'date' in daily_df.columns:
            daily_df['date'] = pd.to_datetime(daily_df['date'])
        
        # 排序
        daily_df = daily_df.sort_values('date').reset_index(drop=True)
        
        # 计算累计收益
        if 'total_value' in daily_df.columns:
            daily_df['cumulative_return'] = (daily_df['total_value'] / daily_df['total_value'].iloc[0]) - 1
        
        # 保存CSV
        filename = f"{prefix}_records_{self.timestamp}.csv"
        filepath = self.output_dir / filename
        daily_df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"💾 每日记录已保存: {filepath}")
        print(f"  记录数量: {len(daily_df)}")
        print(f"  时间范围: {daily_df['date'].min().date()} 至 {daily_df['date'].max().date()}")
        
        return filepath
    
    def export_trade_history(self, trade_df, prefix="trade"):
        """
        导出交易历史
        
        Args:
            trade_df: 交易历史DataFrame
            prefix: 文件前缀
            
        Returns:
            保存的文件路径
        """
        if trade_df.empty:
            print("⚠️  无交易历史数据可导出")
            return None
        
        # 确保日期列是datetime类型
        if 'date' in trade_df.columns:
            trade_df['date'] = pd.to_datetime(trade_df['date'])
        
        # 排序
        trade_df = trade_df.sort_values('date').reset_index(drop=True)
        
        # 保存CSV
        filename = f"{prefix}_history_{self.timestamp}.csv"
        filepath = self.output_dir / filename
        trade_df.to_csv(filepath, index=False, encoding='utf-8-sig')
        
        print(f"💾 交易历史已保存: {filepath}")
        print(f"  交易次数: {len(trade_df)}")
        print(f"  买入交易: {len(trade_df[trade_df['action'] == 'BUY'])}")
        print(f"  卖出交易: {len(trade_df[trade_df['action'] == 'SELL'])}")
        
        return filepath
    
    def export_statistics(self, stats, prefix="statistics"):
        """
        导出统计信息
        
        Args:
            stats: 统计信息字典
            prefix: 文件前缀
            
        Returns:
            保存的文件路径
        """
        if not stats:
            print("⚠️  无统计信息可导出")
            return None
        
        # 保存为文本文件
        txt_filename = f"{prefix}_{self.timestamp}.txt"
        txt_filepath = self.output_dir / txt_filename
        
        with open(txt_filepath, 'w', encoding='utf-8') as f:
            f.write("策略回测统计报告\n")
            f.write("=" * 60 + "\n")
            f.write(f"生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"策略组合: weekly_mean_down + cross_ma50\n")
            f.write("\n")
            
            # 回测参数
            f.write("回测参数:\n")
            f.write("-" * 40 + "\n")
            f.write(f"初始资金: {stats.get('initial_capital', 0):.2f}元\n")
            f.write(f"最大持仓: {stats.get('max_positions', 3)}只\n")
            f.write(f"价格上限: {stats.get('max_price', 150.0)}元\n")
            f.write(f"交易日数: {stats.get('trading_days', 0)}天\n")
            f.write("\n")
            
            # 财务表现
            f.write("财务表现:\n")
            f.write("-" * 40 + "\n")
            f.write(f"最终总资产: {stats.get('final_total_value', 0):.2f}元\n")
            f.write(f"最终现金: {stats.get('final_cash', 0):.2f}元\n")
            f.write(f"总收益: {stats.get('total_profit', 0):.2f}元\n")
            
            if 'initial_capital' in stats:
                total_return = stats.get('final_total_value', 0) - stats['initial_capital']
                return_rate = total_return / stats['initial_capital'] if stats['initial_capital'] > 0 else 0
                f.write(f"总收益率: {return_rate:.1%}\n")
            
            f.write("\n")
            
            # 交易统计
            f.write("交易统计:\n")
            f.write("-" * 40 + "\n")
            f.write(f"总交易次数: {stats.get('total_trades', 0)}\n")
            f.write(f"买入交易: {stats.get('buy_trades', 0)}\n")
            f.write(f"卖出交易: {stats.get('sell_trades', 0)}\n")
            f.write(f"胜率: {stats.get('win_rate', 0):.1%}\n")
            f.write(f"平均每笔盈利: {stats.get('avg_profit_per_trade', 0):.2f}元\n")
            f.write(f"最大盈利: {stats.get('max_profit', 0):.2f}元\n")
            f.write(f"最大亏损: {stats.get('max_loss', 0):.2f}元\n")
            f.write("\n")
            
            # 风险指标
            f.write("风险指标:\n")
            f.write("-" * 40 + "\n")
            if 'daily_values' in stats and not stats['daily_values'].empty:
                daily_returns = stats['daily_values']['total_value'].pct_change().dropna()
                if len(daily_returns) > 0:
                    volatility = daily_returns.std() * np.sqrt(252)
                    sharpe_ratio = (daily_returns.mean() * 252) / (daily_returns.std() * np.sqrt(252)) if daily_returns.std() > 0 else 0
                    
                    f.write(f"年化波动率: {volatility:.1%}\n")
                    f.write(f"夏普比率: {sharpe_ratio:.2f}\n")
        
        print(f"💾 统计报告已保存: {txt_filepath}")
        
        # 同时保存为JSON文件
        json_filename = f"{prefix}_{self.timestamp}.json"
        json_filepath = self.output_dir / json_filename
        
        with open(json_filepath, 'w', encoding='utf-8') as f:
            json.dump(stats, f, ensure_ascii=False, indent=2, default=str)
        
        print(f"💾 JSON数据已保存: {json_filepath}")
        
        return txt_filepath, json_filepath
    
    def plot_equity_curve(self, daily_df, prefix="equity"):
        """
        绘制资金曲线
        
        Args:
            daily_df: 每日记录DataFrame
            prefix: 文件前缀
            
        Returns:
            保存的图片路径
        """
        if daily_df.empty or 'total_value' not in daily_df.columns:
            print("⚠️  无法绘制资金曲线，数据不足")
            return None
        
        # 准备数据
        daily_df = daily_df.sort_values('date').reset_index(drop=True)
        dates = daily_df['date']
        equity = daily_df['total_value']
        
        # 创建图表
        plt.figure(figsize=(12, 6))
        
        # 绘制资金曲线
        plt.plot(dates, equity, 'b-', linewidth=2, label='总资产')
        
        # 添加初始资金线
        initial_value = equity.iloc[0]
        plt.axhline(y=initial_value, color='r', linestyle='--', alpha=0.5, label=f'初始资金: {initial_value:.0f}元')
        
        # 计算并标注最终价值
        final_value = equity.iloc[-1]
        plt.scatter(dates.iloc[-1], final_value, color='g', s=100, zorder=5)
        plt.annotate(f'最终: {final_value:.0f}元', 
                    xy=(dates.iloc[-1], final_value),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=10, color='g')
        
        # 计算收益率
        return_rate = (final_value - initial_value) / initial_value
        
        # 设置图表属性
        plt.title(f'策略资金曲线 (收益率: {return_rate:.1%})', fontsize=14, fontweight='bold')
        plt.xlabel('日期', fontsize=12)
        plt.ylabel('总资产 (元)', fontsize=12)
        plt.grid(True, alpha=0.3)
        plt.legend(loc='best')
        
        # 格式化x轴日期
        plt.gcf().autofmt_xdate()
        
        # 保存图片
        filename = f"{prefix}_curve_{self.timestamp}.png"
        filepath = self.output_dir / filename
        plt.tight_layout()
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"📈 资金曲线图已保存: {filepath}")
        
        return filepath
    
    def plot_trade_analysis(self, trade_df, prefix="trade_analysis"):
        """
        绘制交易分析图
        
        Args:
            trade_df: 交易历史DataFrame
            prefix: 文件前缀
            
        Returns:
            保存的图片路径
        """
        if trade_df.empty or 'profit' not in trade_df.columns:
            print("⚠️  无法绘制交易分析图，数据不足")
            return None
        
        # 只分析卖出交易
        sell_trades = trade_df[trade_df['action'] == 'SELL']
        
        if sell_trades.empty:
            print("⚠️  无卖出交易可分析")
            return None
        
        # 创建图表
        fig, axes = plt.subplots(2, 2, figsize=(14, 10))
        
        # 1. 交易盈亏分布
        ax1 = axes[0, 0]
        profits = sell_trades['profit']
        
        # 分类
        win_trades = profits[profits > 0]
        loss_trades = profits[profits <= 0]
        
        categories = ['盈利交易', '亏损交易', '持平交易']
        counts = [
            len(win_trades),
            len(loss_trades[loss_trades < 0]),
            len(loss_trades[loss_trades == 0])
        ]
        
        colors = ['#4CAF50', '#F44336', '#FFC107']
        ax1.bar(categories, counts, color=colors)
        ax1.set_title('交易盈亏分布', fontsize=12, fontweight='bold')
        ax1.set_ylabel('交易次数', fontsize=10)
        
        # 在柱子上添加数值
        for i, count in enumerate(counts):
            ax1.text(i, count + 0.5, str(count), ha='center', va='bottom', fontsize=10)
        
        # 2. 累计收益曲线
        ax2 = axes[0, 1]
        sell_trades = sell_trades.sort_values('date')
        cumulative_profit = sell_trades['profit'].cumsum()
        
        ax2.plot(sell_trades['date'], cumulative_profit, 'g-', linewidth=2)
        ax2.fill_between(sell_trades['date'], 0, cumulative_profit, alpha=0.3, color='g')
        ax2.set_title('累计收益曲线', fontsize=12, fontweight='bold')
        ax2.set_xlabel('日期', fontsize=10)
        ax2.set_ylabel('累计收益 (元)', fontsize=10)
        ax2.grid(True, alpha=0.3)
        
        # 标注最终收益
        final_profit = cumulative_profit.iloc[-1]
        ax2.scatter(sell_trades['date'].iloc[-1], final_profit, color='r', s=50)
        ax2.annotate(f'{final_profit:.0f}元', 
                    xy=(sell_trades['date'].iloc[-1], final_profit),
                    xytext=(10, 10), textcoords='offset points',
                    fontsize=10, color='r')
        
        # 3. 单笔交易盈亏分布
        ax3 = axes[1, 0]
        
        if not profits.empty:
            # 创建直方图
            n_bins = min(20, len(profits))
            ax3.hist(profits, bins=n_bins, edgecolor='black', alpha=0.7)
            ax3.axvline(x=0, color='r', linestyle='--', alpha=0.7)
            ax3.set_title('单笔交易盈亏分布', fontsize=12, fontweight='bold')
            ax3.set_xlabel('盈亏金额 (元)', fontsize=10)
            ax3.set_ylabel('频次', fontsize=10)
            ax3.grid(True, alpha=0.3)
        
        # 4. 胜率分析
        ax4 = axes[1, 1]
        
        win_rate = len(win_trades) / len(sell_trades) if len(sell_trades) > 0 else 0
        avg_win = win_trades.mean() if len(win_trades) > 0 else 0
        avg_loss = loss_trades.mean() if len(loss_trades) > 0 else 0
        
        metrics = ['胜率', '平均盈利', '平均亏损']
        values = [win_rate, avg_win, avg_loss]
        colors_metrics = ['#2196F3', '#4CAF50', '#F44336']
        
        bars = ax4.bar(metrics, values, color=colors_metrics)
        ax4.set_title('交易质量分析', fontsize=12, fontweight='bold')
        ax4.set_ylabel('数值', fontsize=10)
        
        # 格式化显示
        for i, (bar, val) in enumerate(zip(bars, values)):
            if i == 0:  # 胜率
                text = f'{val:.1%}'
            else:  # 金额
                text = f'{val:.0f}元'
            
            ax4.text(bar.get_x() + bar.get_width()/2, bar.get_height() + (0.01 * max(values)), 
                    text, ha='center', va='bottom', fontsize=10)
        
        plt.tight_layout()
        
        # 保存图片
        filename = f"{prefix}_{self.timestamp}.png"
        filepath = self.output_dir / filename
        plt.savefig(filepath, dpi=150, bbox_inches='tight')
        plt.close()
        
        print(f"📊 交易分析图已保存: {filepath}")
        
        return filepath
    
    def generate_comprehensive_report(self, daily_df, trade_df, stats, strategy_name="weekly_mean_down+cross_ma50"):
        """
        生成综合报告
        
        Args:
            daily_df: 每日记录DataFrame
            trade_df: 交易历史DataFrame
            stats: 统计信息字典
            strategy_name: 策略名称
            
        Returns:
            保存的所有文件路径
        """
        print("📋 生成综合报告...")
        
        results = {}
        
        # 1. 导出每日记录
        daily_file = self.export_daily_records(daily_df)
        results['daily_file'] = daily_file
        
        # 2. 导出交易历史
        trade_file = self.export_trade_history(trade_df)
        results['trade_file'] = trade_file
        
        # 3. 导出统计信息
        if stats:
            txt_file, json_file = self.export_statistics(stats)
            results['stats_txt_file'] = txt_file
            results['stats_json_file'] = json_file
        
        # 4. 绘制资金曲线
        if not daily_df.empty:
            equity_file = self.plot_equity_curve(daily_df)
            results['equity_file'] = equity_file
        
        # 5. 绘制交易分析
        if not trade_df.empty:
            trade_analysis_file = self.plot_trade_analysis(trade_df)
            results['trade_analysis_file'] = trade_analysis_file
        
        # 6. 生成HTML报告
        html_file = self._generate_html_report(daily_df, trade_df, stats, strategy_name)
        results['html_report'] = html_file
        
        print("✅ 综合报告生成完成")
        
        return results
    
    def _generate_html_report(self, daily_df, trade_df, stats, strategy_name):
        """
        生成HTML报告
        
        Args:
            daily_df: 每日记录DataFrame
            trade_df: 交易历史DataFrame
            stats: 统计信息字典
            strategy_name: 策略名称
            
        Returns:
            HTML文件路径
        """
        # 准备数据
        if not daily_df.empty:
            daily_df = daily_df.sort_values('date')
            start_date = daily_df['date'].iloc[0].date()
            end_date = daily_df['date'].iloc[-1].date()
            trading_days = len(daily_df)
            
            initial_value = daily_df['total_value'].iloc[0]
            final_value = daily_df['total_value'].iloc[-1]
            total_return = final_value - initial_value
            return_rate = total_return / initial_value if initial_value > 0 else 0
            
            # 计算年化收益率
            days_held = (end_date - start_date).days
            years_held = days_held / 365.25
            annualized_return = (1 + return_rate) ** (1 / years_held) - 1 if years_held > 0 else 0
        else:
            start_date = "N/A"
            end_date = "N/A"
            trading_days = 0
            initial_value = stats.get('initial_capital', 0)
            final_value = stats.get('final_total_value', 0)
            total_return = final_value - initial_value
            return_rate = total_return / initial_value if initial_value > 0 else 0
            annualized_return = 0
        
        # 交易统计
        if not trade_df.empty:
            total_trades = len(trade_df)
            buy_trades = len(trade_df[trade_df['action'] == 'BUY'])
            sell_trades = len(trade_df[trade_df['action'] == 'SELL'])
            
            sell_trades_df = trade_df[trade_df['action'] == 'SELL']
            if not sell_trades_df.empty:
                win_trades = len(sell_trades_df[sell_trades_df['profit'] > 0])
                win_rate = win_trades / len(sell_trades_df)
                total_profit = sell_trades_df['profit'].sum()
                avg_profit = sell_trades_df['profit'].mean()
                max_profit = sell_trades_df['profit'].max()
                max_loss = sell_trades_df['profit'].min()
            else:
                win_rate = 0
                total_profit = 0
                avg_profit = 0
                max_profit = 0
                max_loss = 0
        else:
            total_trades = 0
            buy_trades = 0
            sell_trades = 0
            win_rate = 0
            total_profit = 0
            avg_profit = 0
            max_profit = 0
            max_loss = 0
        
        # 生成HTML
        html_content = f"""
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>策略回测报告 - {strategy_name}</title>
    <style>
        body {{
            font-family: 'Microsoft YaHei', Arial, sans-serif;
            line-height: 1.6;
            color: #333;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
            text-align: center;
        }}
        .header h1 {{
            margin: 0;
            font-size: 2.5em;
        }}
        .header .subtitle {{
            font-size: 1.2em;
            opacity: 0.9;
            margin-top: 10px;
        }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 25px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .section h2 {{
            color: #2c3e50;
            border-bottom: 3px solid #3498db;
            padding-bottom: 10px;
            margin-top: 0;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-top: 20px;
        }}
        .stat-card {{
            background: #f8f9fa;
            padding: 20px;
            border-radius: 8px;
            border-left: 4px solid #3498db;
        }}
        .stat-card.good {{
            border-left-color: #2ecc71;
        }}
        .stat-card.warning {{
            border-left-color: #f39c12;
        }}
        .stat-card.danger {{
            border-left-color: #e74c3c;
        }}
        .stat-card .value {{
            font-size: 2em;
            font-weight: bold;
            margin: 10px 0;
        }}
        .stat-card .label {{
            color: #7f8c8d;
            font-size: 0.9em;
        }}
        .image-container {{
            text-align: center;
            margin: 20px 0;
        }}
        .image-container img {{
            max-width: 100%;
            border-radius: 8px;
            box-shadow: 0 4px 8px rgba(0,0,0,0.1);
        }}
        .footer {{
            text-align: center;
            margin-top: 40px;
            color: #7f8c8d;
            font-size: 0.9em;
            border-top: 1px solid #eee;
            padding-top: 20px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #f2f2f2;
            font-weight: bold;
        }}
        tr:hover {{
            background-color: #f5f5f5;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>策略回测报告</h1>
        <div class="subtitle">{strategy_name} | 生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</div>
    </div>
    
    <div class="section">
        <h2>📊 回测概览</h2>
        <div class="stats-grid">
            <div class="stat-card good">
                <div class="label">初始资金</div>
                <div class="value">¥{initial_value:,.0f}</div>
            </div>
            <div class="stat-card good">
                <div class="label">最终总资产</div>
                <div class="value">¥{final_value:,.0f}</div>
            </div>
            <div class="stat-card { 'good' if total_return > 0 else 'danger' }">
                <div class="label">总收益</div>
                <div class="value">¥{total_return:+,.0f}</div>
            </div>
            <div class="stat-card { 'good' if return_rate > 0 else 'danger' }">
                <div class="label">总收益率</div>
                <div class="value">{return_rate:+.1%}</div>
            </div>
            <div class="stat-card">
                <div class="label">年化收益率</div>
                <div class="value">{annualized_return:+.1%}</div>
            </div>
            <div class="stat-card">
                <div class="label">交易日数</div>
                <div class="value">{trading_days}</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>📈 资金曲线</h2>
        <div class="image-container">
            <img src="equity_curve_{self.timestamp}.png" alt="资金曲线图">
        </div>
        <p>回测期间: {start_date} 至 {end_date}</p>
    </div>
    
    <div class="section">
        <h2>💹 交易分析</h2>
        <div class="image-container">
            <img src="trade_analysis_{self.timestamp}.png" alt="交易分析图">
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="label">总交易次数</div>
                <div class="value">{total_trades}</div>
            </div>
            <div class="stat-card">
                <div class="label">买入交易</div>
                <div class="value">{buy_trades}</div>
            </div>
            <div class="stat-card">
                <div class="label">卖出交易</div>
                <div class="value">{sell_trades}</div>
            </div>
            <div class="stat-card { 'good' if win_rate > 0.5 else 'warning' }">
                <div class="label">胜率</div>
                <div class="value">{win_rate:.1%}</div>
            </div>
            <div class="stat-card { 'good' if total_profit > 0 else 'danger' }">
                <div class="label">总盈利</div>
                <div class="value">¥{total_profit:+,.0f}</div>
            </div>
            <div class="stat-card { 'good' if avg_profit > 0 else 'danger' }">
                <div class="label">平均每笔盈利</div>
                <div class="value">¥{avg_profit:+,.0f}</div>
            </div>
        </div>
    </div>
    
    <div class="section">
        <h2>📋 详细数据</h2>
        <p>详细数据文件:</p>
        <ul>
            <li>每日记录: <a href="daily_records_{self.timestamp}.csv">daily_records_{self.timestamp}.csv</a></li>
            <li>交易历史: <a href="trade_history_{self.timestamp}.csv">trade_history_{self.timestamp}.csv</a></li>
            <li>统计报告: <a href="statistics_{self.timestamp}.txt">statistics_{self.timestamp}.txt</a></li>
            <li>JSON数据: <a href="statistics_{self.timestamp}.json">statistics_{self.timestamp}.json</a></li>
        </ul>
    </div>
    
    <div class="footer">
        <p>报告生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>策略组合: {strategy_name} | 最大持仓: {stats.get('max_positions', 3)}只 | 价格上限: ¥{stats.get('max_price', 150.0):.0f}</p>
    </div>
</body>
</html>
"""
        
        # 保存HTML文件
        filename = f"report_{self.timestamp}.html"
        filepath = self.output_dir / filename
        
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        print(f"🌐 HTML报告已保存: {filepath}")
        
        return filepath

def main():
    """测试结果导出器"""
    import argparse
    
    parser = argparse.ArgumentParser(description='结果导出器测试')
    parser.add_argument('--output-dir', type=str, default='test_results',
                       help='输出目录 (默认: test_results)')
    
    args = parser.parse_args()
    
    # 创建结果导出器
    exporter = ResultsExporter(output_dir=args.output_dir)
    
    # 创建测试数据
    dates = pd.date_range(start='2025-01-01', end='2025-06-01', freq='B')
    daily_df = pd.DataFrame({
        'date': dates,
        'cash': np.random.uniform(10000, 50000, len(dates)),
        'position_count': np.random.randint(0, 4, len(dates)),
        'total_value': np.random.uniform(45000, 55000, len(dates))
    })
    
    # 创建测试交易数据
    trade_dates = dates[np.random.choice(len(dates), 10, replace=False)]
    trade_df = pd.DataFrame({
        'date': trade_dates,
        'stock_code': [f'{i:06d}' for i in range(10)],
        'action': np.random.choice(['BUY', 'SELL'], 10),
        'shares': np.random.randint(100, 1000, 10),
        'price': np.random.uniform(10, 100, 10),
        'amount': np.random.uniform(1000, 50000, 10),
        'fee': np.random.uniform(5, 50, 10),
        'profit': np.random.uniform(-5000, 5000, 10),
        'reason': np.random.choice(['止盈', '止损', '策略买入', '持有到期'], 10)
    })
    
    # 创建测试统计信息
    stats = {
        'initial_capital': 50000,
        'final_total_value': 55000,
        'final_cash': 10000,
        'total_profit': 5000,
        'total_trades': 10,
        'buy_trades': 5,
        'sell_trades': 5,
        'win_rate': 0.6,
        'avg_profit_per_trade': 500,
        'max_profit': 2000,
        'max_loss': -1000,
        'trading_days': len(dates),
        'max_positions': 3,
        'max_price': 150.0
    }
    
    # 测试导出功能
    print("🧪 测试结果导出器...")
    
    daily_file = exporter.export_daily_records(daily_df)
    trade_file = exporter.export_trade_history(trade_df)
    stats_files = exporter.export_statistics(stats)
    equity_file = exporter.plot_equity_curve(daily_df)
    trade_analysis_file = exporter.plot_trade_analysis(trade_df)
    
    # 生成综合报告
    results = exporter.generate_comprehensive_report(daily_df, trade_df, stats)
    
    print("\n✅ 测试完成")
    print(f"所有文件已保存到: {args.output_dir}")

if __name__ == "__main__":
    main()