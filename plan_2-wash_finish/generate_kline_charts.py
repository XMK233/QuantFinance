#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import gridspec
import numpy as np
from datetime import datetime
import glob

class KLineChartGenerator:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.output_dir = "/mnt/d/forCoding_code/QuantFinance/plan_2-wash_finish/charts"
        os.makedirs(self.output_dir, exist_ok=True)
    
    def find_stock_file(self, stock_code):
        """查找股票数据文件"""
        # 尝试不同的文件名格式
        patterns = [
            f"{stock_code}.csv",
            f"sh.{stock_code}.csv",
            f"sz.{stock_code}.csv"
        ]
        
        for pattern in patterns:
            file_path = os.path.join(self.data_dir, pattern)
            if os.path.exists(file_path):
                return file_path
        
        # 如果没有找到精确匹配，尝试模糊搜索
        search_patterns = [
            f"*{stock_code}*.csv",
            f"*sh*{stock_code}*.csv",
            f"*sz*{stock_code}*.csv"
        ]
        
        for pattern in search_patterns:
            files = glob.glob(os.path.join(self.data_dir, pattern))
            if files:
                return files[0]
        
        return None
    
    def load_stock_data(self, stock_code):
        """加载股票数据"""
        file_path = self.find_stock_file(stock_code)
        if not file_path:
            print(f"未找到股票 {stock_code} 的数据文件")
            return None
        
        try:
            df = pd.read_csv(file_path)
            
            # 确保日期列格式正确
            if 'date' in df.columns:
                df['date'] = pd.to_datetime(df['date'])
                df = df.sort_values('date')
            
            # 确保数值列格式正确
            numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
            for col in numeric_cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            # 移除包含NaN的行
            df = df.dropna(subset=['close', 'volume', 'open', 'high', 'low'])
            
            if len(df) < 20:
                print(f"股票 {stock_code} 数据量不足")
                return None
            
            return df
            
        except Exception as e:
            print(f"加载股票 {stock_code} 数据时出错: {e}")
            return None
    
    def calculate_technical_indicators(self, df):
        """计算技术指标"""
        df = df.copy()
        
        # 移动平均线
        df['MA5'] = df['close'].rolling(window=5).mean()
        df['MA20'] = df['close'].rolling(window=20).mean()
        df['MA60'] = df['close'].rolling(window=60).mean()
        
        # RSI
        delta = df['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        
        # MACD
        exp12 = df['close'].ewm(span=12, adjust=False).mean()
        exp26 = df['close'].ewm(span=26, adjust=False).mean()
        df['MACD'] = exp12 - exp26
        df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
        df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
        
        # 布林带
        df['BB_Middle'] = df['close'].rolling(window=20).mean()
        bb_std = df['close'].rolling(window=20).std()
        df['BB_Upper'] = df['BB_Middle'] + (bb_std * 2)
        df['BB_Lower'] = df['BB_Middle'] - (bb_std * 2)
        
        return df
    
    def create_kline_chart(self, df, stock_code, stock_name):
        """创建K线图"""
        if df is None or len(df) < 20:
            return False
        
        # 计算技术指标
        df = self.calculate_technical_indicators(df)
        
        # 创建图表
        fig = plt.figure(figsize=(16, 12))
        gs = gridspec.GridSpec(4, 1, height_ratios=[3, 1, 1, 1])
        
        # 设置中文字体
        plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
        plt.rcParams['axes.unicode_minus'] = False
        
        # 1. K线图
        ax1 = plt.subplot(gs[0])
        
        # 绘制K线
        dates = mdates.date2num(df['date'])
        
        # 上涨和下跌的K线
        rise = df[df['close'] >= df['open']]
        fall = df[df['close'] < df['open']]
        
        # 绘制上涨K线（红色）
        ax1.bar(mdates.date2num(rise['date']), 
                rise['close'] - rise['open'], 
                bottom=rise['open'], 
                color='red', width=0.6, alpha=0.7)
        ax1.bar(mdates.date2num(rise['date']), 
                rise['high'] - rise['close'], 
                bottom=rise['close'], 
                color='red', width=0.1, alpha=0.7)
        ax1.bar(mdates.date2num(rise['date']), 
                rise['open'] - rise['low'], 
                bottom=rise['low'], 
                color='red', width=0.1, alpha=0.7)
        
        # 绘制下跌K线（绿色）
        ax1.bar(mdates.date2num(fall['date']), 
                fall['open'] - fall['close'], 
                bottom=fall['close'], 
                color='green', width=0.6, alpha=0.7)
        ax1.bar(mdates.date2num(fall['date']), 
                fall['high'] - fall['open'], 
                bottom=fall['open'], 
                color='green', width=0.1, alpha=0.7)
        ax1.bar(mdates.date2num(fall['date']), 
                fall['close'] - fall['low'], 
                bottom=fall['low'], 
                color='green', width=0.1, alpha=0.7)
        
        # 绘制移动平均线
        ax1.plot(dates, df['MA5'], 'blue', linewidth=1, label='MA5')
        ax1.plot(dates, df['MA20'], 'orange', linewidth=1.5, label='MA20')
        ax1.plot(dates, df['MA60'], 'purple', linewidth=2, label='MA60')
        
        # 绘制布林带
        ax1.plot(dates, df['BB_Upper'], 'gray', linewidth=1, alpha=0.7, label='BB Upper')
        ax1.plot(dates, df['BB_Middle'], 'black', linewidth=1, alpha=0.7, label='BB Middle')
        ax1.plot(dates, df['BB_Lower'], 'gray', linewidth=1, alpha=0.7, label='BB Lower')
        ax1.fill_between(dates, df['BB_Upper'], df['BB_Lower'], color='gray', alpha=0.1)
        
        ax1.set_title(f'{stock_name} ({stock_code}) - K线图', fontsize=16, fontweight='bold')
        ax1.legend(loc='upper left')
        ax1.grid(True, alpha=0.3)
        ax1.set_ylabel('价格')
        
        # 2. 成交量
        ax2 = plt.subplot(gs[1], sharex=ax1)
        ax2.bar(mdates.date2num(df['date']), df['volume'], 
                color=['red' if close >= open else 'green' for close, open in zip(df['close'], df['open'])], 
                alpha=0.7, width=0.6)
        ax2.set_ylabel('成交量')
        ax2.grid(True, alpha=0.3)
        
        # 3. MACD
        ax3 = plt.subplot(gs[2], sharex=ax1)
        ax3.plot(dates, df['MACD'], 'blue', linewidth=1, label='MACD')
        ax3.plot(dates, df['MACD_Signal'], 'red', linewidth=1, label='Signal')
        ax3.bar(dates, df['MACD_Histogram'], 
                color=['red' if x >= 0 else 'green' for x in df['MACD_Histogram']], 
                alpha=0.7, width=0.6)
        ax3.axhline(0, color='black', linestyle='-', alpha=0.3)
        ax3.set_ylabel('MACD')
        ax3.legend(loc='upper left')
        ax3.grid(True, alpha=0.3)
        
        # 4. RSI
        ax4 = plt.subplot(gs[3], sharex=ax1)
        ax4.plot(dates, df['RSI'], 'purple', linewidth=1, label='RSI')
        ax4.axhline(70, color='red', linestyle='--', alpha=0.7, label='超买线 (70)')
        ax4.axhline(30, color='green', linestyle='--', alpha=0.7, label='超卖线 (30)')
        ax4.axhline(50, color='gray', linestyle='-', alpha=0.3, label='中线 (50)')
        ax4.set_ylabel('RSI')
        ax4.set_xlabel('日期')
        ax4.legend(loc='upper left')
        ax4.grid(True, alpha=0.3)
        
        # 格式化x轴日期
        for ax in [ax1, ax2, ax3, ax4]:
            ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
            ax.xaxis.set_major_locator(mdates.MonthLocator())
        
        plt.tight_layout()
        
        # 保存图表
        chart_path = os.path.join(self.output_dir, f"{stock_code}_{stock_name}_kline_chart.png")
        plt.savefig(chart_path, dpi=300, bbox_inches='tight')
        plt.close()
        
        print(f"已生成 {stock_name} ({stock_code}) 的K线图: {chart_path}")
        return True
    
    def generate_charts_for_stocks(self, stock_list):
        """为股票列表生成图表"""
        success_count = 0
        
        for stock_info in stock_list:
            stock_code = stock_info['code']
            stock_name = stock_info['name']
            
            print(f"正在处理 {stock_name} ({stock_code})...")
            
            # 加载数据
            try:
                df = self.load_stock_data(stock_code)
                if df is None:
                    continue
                
                # 生成图表
                if self.create_kline_chart(df, stock_code, stock_name):
                    success_count += 1
            except Exception as e:
                print(f"处理 {stock_name} ({stock_code}) 时出错: {e}")
                continue
        
        print(f"\n成功生成 {success_count}/{len(stock_list)} 只股票的K线图")
        print(f"图表保存在: {self.output_dir}")

def parse_report_file(file_path):
    """从分析报告中解析股票列表"""
    stocks = []
    if not os.path.exists(file_path):
        print(f"报告文件不存在: {file_path}")
        return stocks
        
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                # 匹配格式: "第1名: 广百股份 (002187)"
                if line.startswith('第') and '名:' in line:
                    try:
                        # 提取冒号后的内容
                        parts = line.split(':', 1)
                        if len(parts) >= 2:
                            content = parts[1].strip()
                            # content 应该是 "广百股份 (002187)"
                            # 查找最后一个左括号
                            last_open_paren = content.rfind('(')
                            if last_open_paren != -1 and content.endswith(')'):
                                name = content[:last_open_paren].strip()
                                code = content[last_open_paren+1:-1].strip()
                                stocks.append({"code": code, "name": name})
                    except Exception as e:
                        print(f"解析行出错: {line}, 错误: {e}")
    except Exception as e:
        print(f"读取报告文件出错: {e}")
        
    return stocks

def main():
    # 报告文件路径
    report_path = "/mnt/d/forCoding_code/QuantFinance/plan_2-wash_finish/stock_analysis_report.txt"
    
    print(f"正在从报告读取股票列表: {report_path}")
    recommended_stocks = parse_report_file(report_path)
    
    if not recommended_stocks:
        print("未从报告中找到股票，请检查报告格式或路径。")
        # 如果报告为空，使用默认列表测试
        print("使用默认列表进行测试...")
        recommended_stocks = [
            {"code": "605365", "name": "立达信"},
            {"code": "688111", "name": "金山办公"},
            {"code": "688698", "name": "伟创电气"},
            {"code": "002187", "name": "广百股份"},
            {"code": "000908", "name": "*ST景峰"}
        ]
    else:
        print(f"找到 {len(recommended_stocks)} 只股票")
    
    # 数据目录
    data_dir = "/mnt/d/forCoding_data/QuantFinance/plan_1-select_stock_by_week/originalData"
    
    # 创建图表生成器
    chart_generator = KLineChartGenerator(data_dir)
    
    # 生成图表
    chart_generator.generate_charts_for_stocks(recommended_stocks)

if __name__ == "__main__":
    main()