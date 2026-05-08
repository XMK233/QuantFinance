#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sqlite3
import pandas as pd
from datetime import datetime, timedelta
import os
from typing import List, Dict, Optional

class StockDatabase:
    def __init__(self, db_path: str = None):
        """初始化股票数据库"""
        if db_path is None:
            # 默认数据库路径在数据目录
            self.db_path = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_data.db"
        else:
            self.db_path = db_path
        
        # 确保目录存在
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.init_database()
    
    def init_database(self):
        """初始化数据库表结构"""
        with sqlite3.connect(self.db_path) as conn:
            # 股票基本信息表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    industry TEXT,
                    market TEXT,
                    listing_date TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 股票日线数据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_daily (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    turnover_rate REAL,
                    pe_ratio REAL,
                    pb_ratio REAL,
                    FOREIGN KEY (stock_code) REFERENCES stocks(code),
                    UNIQUE(stock_code, date)
                )
            """)
            
            # 股票周线数据表
            conn.execute("""
                CREATE TABLE IF NOT EXISTS stock_weekly (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stock_code TEXT NOT NULL,
                    date TEXT NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume REAL,
                    amount REAL,
                    turnover_rate REAL,
                    pe_ratio REAL,
                    pb_ratio REAL,
                    FOREIGN KEY (stock_code) REFERENCES stocks(code),
                    UNIQUE(stock_code, date)
                )
            """)
            
            # 创建索引
            conn.execute("CREATE INDEX IF NOT EXISTS idx_daily_code_date ON stock_daily(stock_code, date)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_weekly_code_date ON stock_weekly(stock_code, date)")
    
    def get_max_date(self, stock_code: str, frequency: str = 'daily') -> Optional[str]:
        """获取某只股票在数据库中的最新日期"""
        table_name = 'stock_daily' if frequency == 'daily' else 'stock_weekly'
        
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                f"SELECT MAX(date) FROM {table_name} WHERE stock_code = ?", 
                (stock_code,)
            ).fetchone()
            
            return result[0] if result[0] else None
    
    def stock_exists(self, stock_code: str) -> bool:
        """检查股票是否已存在"""
        with sqlite3.connect(self.db_path) as conn:
            result = conn.execute(
                "SELECT 1 FROM stocks WHERE code = ?", 
                (stock_code,)
            ).fetchone()
            return result is not None
    
    def insert_stock_info(self, stock_data: Dict):
        """插入股票基本信息"""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO stocks 
                   (code, name, industry, market, listing_date) 
                   VALUES (?, ?, ?, ?, ?)""",
                (stock_data['code'], stock_data['name'], 
                 stock_data.get('industry'), stock_data.get('market'),
                 stock_data.get('listing_date'))
            )
    
    def insert_price_data(self, data: pd.DataFrame, frequency: str = 'daily', show_progress: bool = True):
        """插入价格数据"""
        table_name = 'stock_daily' if frequency == 'daily' else 'stock_weekly'
        
        with sqlite3.connect(self.db_path) as conn:
            if show_progress:
                from tqdm import tqdm

                with tqdm(total=len(data), desc=f"插入{frequency}数据", leave=False) as pbar:
                    for _, row in data.iterrows():
                        try:
                            conn.execute(
                                f"""INSERT OR REPLACE INTO {table_name} 
                                   (stock_code, date, open, high, low, close, volume, amount, 
                                    turnover_rate, pe_ratio, pb_ratio)
                                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                                (row['code'], row['date'], row.get('open'), row.get('high'), 
                                 row.get('low'), row.get('close'), row.get('volume'), 
                                 row.get('amount'), row.get('turn'), row.get('peTTM'), 
                                 row.get('pbMRQ'))
                            )
                            pbar.update(1)
                            pbar.set_postfix_str(f"{row['code']} {row['date']}")
                        except Exception as e:
                            print(f"插入数据失败: {e}")
            else:
                for _, row in data.iterrows():
                    try:
                        conn.execute(
                            f"""INSERT OR REPLACE INTO {table_name} 
                               (stock_code, date, open, high, low, close, volume, amount, 
                                turnover_rate, pe_ratio, pb_ratio)
                               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                            (row['code'], row['date'], row.get('open'), row.get('high'), 
                             row.get('low'), row.get('close'), row.get('volume'), 
                             row.get('amount'), row.get('turn'), row.get('peTTM'), 
                             row.get('pbMRQ'))
                        )
                    except Exception as e:
                        print(f"插入数据失败: {e}")

            conn.commit()
    
    def get_missing_dates(self, stock_code: str, frequency: str = 'daily', 
                         start_date: str = '2025-01-01') -> List[str]:
        """获取需要补全的日期范围"""
        max_date = self.get_max_date(stock_code, frequency)

        last_trading_day = self._get_available_trading_day()
        if frequency == "weekly":
            last_trading_day = self._get_last_weekly_day(last_trading_day)
        
        if not max_date:
            # 如果数据库中没有该股票的数据，返回完整的时间范围
            return [start_date, last_trading_day.strftime('%Y-%m-%d')]
        
        # 如果已有数据，检查是否需要更新
        max_date_dt = datetime.strptime(max_date, '%Y-%m-%d')
        
        # 如果最新数据已经是最新交易日，说明不需要更新
        if max_date_dt.date() >= last_trading_day:
            return [max_date, max_date]  # 返回相同的日期表示不需要更新
        
        # 从最新日期的下一天开始到最后一个交易日的范围
        next_day = (max_date_dt + timedelta(days=1)).strftime('%Y-%m-%d')
        end_date = last_trading_day.strftime('%Y-%m-%d')
        
        return [next_day, end_date]
    
    def _get_last_trading_day(self):
        """获取最后一个交易日（考虑周末和节假日）"""
        today = datetime.now().date()
        
        # 简单实现：如果是周末，返回上一个周五
        if today.weekday() == 5:  # 周六
            return today - timedelta(days=1)
        elif today.weekday() == 6:  # 周日
            return today - timedelta(days=2)
        else:
            # 周一到周五，如果是交易时间后，返回今天；否则返回上一个交易日
            now = datetime.now()
            # 假设交易时间：9:30-15:00
            if now.hour >= 15 or (now.hour == 14 and now.minute >= 30):
                return today
            else:
                # 交易时间前，返回上一个交易日
                if today.weekday() == 0:  # 周一
                    return today - timedelta(days=3)  # 上周五
                else:
                    return today - timedelta(days=1)
    
    def _get_available_trading_day(self):
        """获取最后一个有数据的交易日（防止请求未来日期）"""
        return self._get_last_trading_day()

    def _get_last_weekly_day(self, last_trading_day):
        delta = (last_trading_day.weekday() - 4) % 7
        return last_trading_day - timedelta(days=delta)

if __name__ == "__main__":
    # 测试数据库初始化
    db = StockDatabase("test_stock.db")
    print("数据库初始化完成")
