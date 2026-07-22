#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
数据管理器
专门处理回测所需的数据获取和日期处理
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import os
import sys
from pathlib import Path
from tqdm import tqdm
import warnings
warnings.filterwarnings('ignore')

# 添加 plan_3-standardization_1 目录到路径
plan3_dir = Path(__file__).parent.parent / "plan_3-standardization_1"
sys.path.insert(0, str(plan3_dir))

from stock_operators.base_operator import BaseOperator
from stock_operators.st_operator import STStockOperator

class DataManager:
    """数据管理器"""
    
    def __init__(self):
        self.base_op = BaseOperator()
        self.st_op = STStockOperator()
        self._trading_dates_cache = None
    
    def get_trading_dates(self, start_date, end_date, force_refresh=False):
        """
        获取交易日历
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            force_refresh: 是否强制刷新缓存
            
        Returns:
            交易日历列表
        """
        if not force_refresh and self._trading_dates_cache is not None:
            # 从缓存中过滤
            mask = (self._trading_dates_cache >= start_date) & (self._trading_dates_cache <= end_date)
            return self._trading_dates_cache[mask]
        
        print("📅 获取交易日历...")
        
        # 获取所有股票代码
        all_codes = self.base_op.get_all_stock_codes(exclude_gem=True, exclude_star=True)
        
        if not all_codes:
            print("  ⚠️  无法获取股票代码，使用工作日历")
            date_range = pd.date_range(start=start_date, end=end_date, freq='B')
            self._trading_dates_cache = date_range
            return date_range
        
        # 使用第一只股票获取交易日历
        sample_code = all_codes[0]
        daily_data = self.base_op.get_daily_data(sample_code, days=2000)
        
        if daily_data is None or daily_data.empty:
            print("  ⚠️  无法获取样本数据，使用工作日历")
            date_range = pd.date_range(start=start_date, end=end_date, freq='B')
            self._trading_dates_cache = date_range
            return date_range
        
        # 提取交易日历
        trading_dates = pd.to_datetime(daily_data['date']).sort_values().unique()
        self._trading_dates_cache = trading_dates
        
        # 过滤日期范围
        mask = (trading_dates >= start_date) & (trading_dates <= end_date)
        filtered_dates = trading_dates[mask]
        
        print(f"  ✅ 获取到 {len(filtered_dates)} 个交易日")
        return filtered_dates
    
    def get_stock_price(self, stock_code, date):
        """
        获取指定日期的股票价格
        
        Args:
            stock_code: 股票代码
            date: 日期
            
        Returns:
            价格字典或None
        """
        # 获取前后几天的数据以确保能获取到指定日期
        daily_data = self.base_op.get_daily_data(stock_code, days=30)
        
        if daily_data is None or daily_data.empty:
            return None
        
        # 转换日期
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        
        # 查找指定日期或最近的前一个交易日
        mask = daily_data['date'] <= date
        if not mask.any():
            return None
        
        # 获取最近的数据
        recent_data = daily_data[mask].iloc[-1]
        
        try:
            price_info = {
                'date': recent_data['date'],
                'open': float(recent_data['open']),
                'high': float(recent_data['high']),
                'low': float(recent_data['low']),
                'close': float(recent_data['close']),
                'volume': float(recent_data['volume']),
                'amount': float(recent_data['amount']) if 'amount' in recent_data else 0
            }
            return price_info
        except (ValueError, TypeError):
            return None
    
    def get_stock_price_history(self, stock_code, start_date, end_date):
        """
        获取股票价格历史
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            DataFrame with price history
        """
        # 计算需要的天数
        days = (end_date - start_date).days + 100  # 加一些缓冲
        
        daily_data = self.base_op.get_daily_data(stock_code, days=days)
        if daily_data is None or daily_data.empty:
            return pd.DataFrame()
        
        # 转换日期和数值
        daily_data['date'] = pd.to_datetime(daily_data['date'])
        
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount']
        for col in numeric_cols:
            if col in daily_data.columns:
                daily_data[col] = pd.to_numeric(daily_data[col], errors='coerce')
        
        # 过滤日期范围
        mask = (daily_data['date'] >= start_date) & (daily_data['date'] <= end_date)
        filtered_data = daily_data[mask].copy()
        
        return filtered_data
    
    def get_stock_basic_info(self, stock_code):
        """
        获取股票基本信息
        
        Args:
            stock_code: 股票代码
            
        Returns:
            基本信息字典
        """
        try:
            # 获取股票名称
            stock_name = self.base_op.get_stock_name(stock_code)
            
            # 检查是否为ST股票
            st_info = self.st_op.calculate(stock_code)
            is_st = st_info.get('is_st', False)
            
            # 获取最新价格
            price_data = self.get_stock_price(stock_code, pd.Timestamp.now())
            current_price = price_data['close'] if price_data else 0
            
            return {
                'stock_code': stock_code,
                'stock_name': stock_name or '',
                'is_st': is_st,
                'current_price': current_price
            }
        except Exception as e:
            print(f"  获取股票 {stock_code} 基本信息失败: {e}")
            return {
                'stock_code': stock_code,
                'stock_name': '',
                'is_st': False,
                'current_price': 0
            }
    
    def get_all_main_board_stocks(self, exclude_gem=True, exclude_star=True):
        """
        获取所有沪深主板股票
        
        Args:
            exclude_gem: 是否排除创业板
            exclude_star: 是否排除科创板
            
        Returns:
            股票代码列表
        """
        return self.base_op.get_all_stock_codes(
            exclude_gem=exclude_gem,
            exclude_star=exclude_star
        )
    
    def filter_stocks_by_price(self, stock_codes, max_price=150.0, min_price=1.0):
        """
        按价格过滤股票
        
        Args:
            stock_codes: 股票代码列表
            max_price: 最高价格
            min_price: 最低价格
            
        Returns:
            过滤后的股票代码列表
        """
        if not stock_codes:
            return []
        
        filtered_codes = []
        
        print(f"💰 按价格过滤股票 ({min_price} ≤ 价格 ≤ {max_price})...")
        pbar = tqdm(stock_codes, desc="价格检查", unit="股票")
        
        for code in pbar:
            price_data = self.get_stock_price(code, pd.Timestamp.now())
            if not price_data:
                continue
            
            current_price = price_data['close']
            if min_price <= current_price <= max_price:
                filtered_codes.append(code)
            
            pbar.set_description(f"价格检查 {len(filtered_codes)}/{len(stock_codes)}")
        
        print(f"  ✅ 价格过滤完成: {len(filtered_codes)}/{len(stock_codes)} 只")
        return filtered_codes
    
    def filter_stocks_by_st(self, stock_codes):
        """
        过滤ST股票
        
        Args:
            stock_codes: 股票代码列表
            
        Returns:
            过滤后的股票代码列表
        """
        if not stock_codes:
            return []
        
        filtered_codes = []
        
        print("🚫 过滤ST股票...")
        pbar = tqdm(stock_codes, desc="ST检查", unit="股票")
        
        for code in pbar:
            try:
                st_info = self.st_op.calculate(code)
                is_st = st_info.get('is_st', False)
                
                if not is_st:
                    filtered_codes.append(code)
            except Exception:
                # 如果检查失败，默认不是ST
                filtered_codes.append(code)
            
            pbar.set_description(f"ST检查 {len(filtered_codes)}/{len(stock_codes)}")
        
        print(f"  ✅ ST过滤完成: {len(filtered_codes)}/{len(stock_codes)} 只")
        return filtered_codes
    
    def get_stock_performance(self, stock_code, start_date, end_date):
        """
        获取股票在指定期间的表现
        
        Args:
            stock_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            
        Returns:
            表现数据字典
        """
        price_history = self.get_stock_price_history(stock_code, start_date, end_date)
        
        if price_history.empty:
            return None
        
        # 计算收益率
        start_price = price_history['close'].iloc[0]
        end_price = price_history['close'].iloc[-1]
        
        total_return = (end_price - start_price) / start_price if start_price > 0 else 0
        
        # 计算波动率
        returns = price_history['close'].pct_change().dropna()
        volatility = returns.std() * np.sqrt(252) if len(returns) > 1 else 0
        
        # 计算最大回撤
        cumulative = (1 + returns).cumprod()
        running_max = cumulative.expanding().max()
        drawdown = (cumulative - running_max) / running_max
        max_drawdown = drawdown.min()
        
        return {
            'stock_code': stock_code,
            'start_price': start_price,
            'end_price': end_price,
            'total_return': total_return,
            'volatility': volatility,
            'max_drawdown': max_drawdown,
            'trading_days': len(price_history)
        }
    
    def save_price_data(self, stock_codes, start_date, end_date, output_dir="price_data"):
        """
        保存股票价格数据
        
        Args:
            stock_codes: 股票代码列表
            start_date: 开始日期
            end_date: 结束日期
            output_dir: 输出目录
            
        Returns:
            保存的文件路径列表
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(exist_ok=True)
        
        saved_files = []
        
        print(f"💾 保存价格数据 ({len(stock_codes)} 只股票)...")
        pbar = tqdm(stock_codes, desc="保存数据", unit="股票")
        
        for code in pbar:
            price_history = self.get_stock_price_history(code, start_date, end_date)
            
            if not price_history.empty:
                filename = f"{code}_price_{start_date.date()}_{end_date.date()}.csv"
                filepath = output_dir / filename
                
                price_history.to_csv(filepath, index=False, encoding='utf-8-sig')
                saved_files.append(filepath)
            
            pbar.set_description(f"保存数据 {len(saved_files)}/{len(stock_codes)}")
        
        print(f"  ✅ 数据保存完成: {len(saved_files)} 个文件")
        return saved_files

def main():
    """测试数据管理器"""
    import argparse
    
    parser = argparse.ArgumentParser(description='数据管理器测试')
    parser.add_argument('--start-date', type=str, default='2025-01-01',
                       help='开始日期 (默认: 2025-01-01)')
    parser.add_argument('--end-date', type=str, default=datetime.now().strftime('%Y-%m-%d'),
                       help='结束日期 (默认: 今天)')
    parser.add_argument('--test-stock', type=str, default='000001',
                       help='测试股票代码 (默认: 000001)')
    
    args = parser.parse_args()
    
    # 创建数据管理器
    dm = DataManager()
    
    # 测试交易日历
    start_date = pd.to_datetime(args.start_date)
    end_date = pd.to_datetime(args.end_date)
    
    trading_dates = dm.get_trading_dates(start_date, end_date)
    print(f"交易日数量: {len(trading_dates)}")
    print(f"第一个交易日: {trading_dates[0].date()}")
    print(f"最后一个交易日: {trading_dates[-1].date()}")
    
    # 测试股票价格
    test_date = trading_dates[0] if len(trading_dates) > 0 else start_date
    price_info = dm.get_stock_price(args.test_stock, test_date)
    
    if price_info:
        print(f"\n股票 {args.test_stock} 在 {test_date.date()} 的价格:")
        print(f"  开盘: {price_info['open']:.2f}")
        print(f"  最高: {price_info['high']:.2f}")
        print(f"  最低: {price_info['low']:.2f}")
        print(f"  收盘: {price_info['close']:.2f}")
        print(f"  成交量: {price_info['volume']:.0f}")
    else:
        print(f"\n无法获取股票 {args.test_stock} 的价格数据")
    
    # 测试股票过滤
    all_stocks = dm.get_all_main_board_stocks()
    print(f"\n沪深主板股票总数: {len(all_stocks)}")
    
    non_st_stocks = dm.filter_stocks_by_st(all_stocks[:100])  # 只测试前100只
    print(f"非ST股票数量: {len(non_st_stocks)}")
    
    price_filtered = dm.filter_stocks_by_price(non_st_stocks, max_price=150.0, min_price=1.0)
    print(f"价格过滤后数量: {len(price_filtered)}")

if __name__ == "__main__":
    main()