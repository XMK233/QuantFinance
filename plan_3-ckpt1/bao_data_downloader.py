#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import baostock as bs
import pandas as pd
import time
import random
from datetime import datetime, timedelta
from concurrent.futures import ProcessPoolExecutor, as_completed
from tqdm import tqdm
from stock_database import StockDatabase
import os
import multiprocessing as mp
import atexit
import signal
import threading

class BaoStockDownloader:
    def __init__(self, db_path=None):
        self.db = StockDatabase(db_path)
        
    def login(self):
        """登录baostock"""
        lg = bs.login()
        if lg.error_code != '0':
            raise Exception(f"登录失败: {lg.error_msg}")
        print("baostock登录成功")
    
    def logout(self):
        """登出baostock"""
        err = {}
        def _do_logout():
            try:
                bs.logout()
            except Exception as e:
                err["e"] = e

        t = threading.Thread(target=_do_logout, daemon=True)
        t.start()
        t.join(timeout=5)
        if t.is_alive():
            print("⚠️ baostock登出超时(5s)，已跳过")
            return
        if "e" in err:
            print(f"⚠️ baostock登出异常: {err['e']}")
            return
        print("baostock已登出")
    
    def get_stock_list(self):
        """获取股票列表"""
        rs = bs.query_stock_basic()
        if rs.error_code != '0':
            raise Exception(f"获取股票列表失败: {rs.error_msg}")
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        # 过滤：只保留上市状态且类型为股票的
        df = df[(df['status'] == '1') & (df['type'] == '1')]
        return df
    
    def download_stock_data(self, stock_code: str, frequency: str = 'd', 
                           start_date: str = '2025-01-01', end_date: str = None):
        """下载单只股票数据"""
        if end_date is None:
            end_date = datetime.now().strftime('%Y-%m-%d')
        
        # 随机休眠避免频繁请求
        time.sleep(random.uniform(0.1, 1.0))
        
        # 构建查询字段 - 使用与 bao_get_single_stock.py 相同的字段
        if frequency == 'w':
            # 周线字段
            fields = "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg"
        else:
            # 日线字段
            fields = "date,code,open,high,low,close,volume,amount,turn,peTTM,pbMRQ"
        
        rs = bs.query_history_k_data_plus(
            stock_code,
            fields,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag="2"  # 前复权
        )
        
        if rs.error_code != '0':
            return None, f"下载失败: {rs.error_msg}"
        
        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return None, "无数据"
        
        df = pd.DataFrame(data_list, columns=rs.fields)
        
        # 转换数据类型
        numeric_cols = ['open', 'high', 'low', 'close', 'volume', 'amount', 'turn', 'peTTM', 'pbMRQ']
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
        
        return df, "成功"
    
    def update_stock_info(self, force_update=False):
        """更新股票基本信息，支持缓存复用"""
        cache_file = "/mnt/d/forCoding_data/QuantFinance/plan_3-standardization_1/stock_list_cache.csv"
        
        # 检查缓存是否存在且不需要强制更新
        if not force_update and os.path.exists(cache_file):
            cache_time = os.path.getmtime(cache_file)
            current_time = time.time()
            # 缓存有效期：7天（604800秒）
            if current_time - cache_time < 604800:
                print("📦 使用缓存的股票列表...")
                stock_list = pd.read_csv(cache_file)
                
                with tqdm(total=len(stock_list), desc="导入缓存股票信息") as pbar:
                    for _, row in stock_list.iterrows():
                        stock_data = {
                            'code': row['code'],
                            'name': row['code_name'],
                            'industry': row.get('industry'),
                            'market': 'SH' if row['code'].startswith('sh') or row['code'].startswith('6') else 'SZ',
                            'listing_date': row.get('ipoDate')
                        }
                        self.db.insert_stock_info(stock_data)
                        pbar.update(1)
                
                print(f"✅ 从缓存导入 {len(stock_list)} 只股票的基本信息")
                return stock_list
        
        print("🔄 正在从baostock获取最新股票基本信息...")
        stock_list = self.get_stock_list()
        
        # 保存到缓存文件
        os.makedirs(os.path.dirname(cache_file), exist_ok=True)
        stock_list.to_csv(cache_file, index=False, encoding='utf-8')
        print(f"💾 股票列表已缓存至: {cache_file}")
        
        with tqdm(total=len(stock_list), desc="更新股票信息") as pbar:
            for _, row in stock_list.iterrows():
                stock_data = {
                    'code': row['code'],
                    'name': row['code_name'],
                    'industry': row.get('industry'),
                    'market': 'SH' if row['code'].startswith('sh') or row['code'].startswith('6') else 'SZ',
                    'listing_date': row.get('ipoDate')
                }
                self.db.insert_stock_info(stock_data)
                pbar.update(1)
                pbar.set_postfix_str(f"已处理: {row['code']}")
        
        print(f"✅ 已更新 {len(stock_list)} 只股票的基本信息")
        return stock_list
    
    def download_and_save_data(self, stock_code: str, frequency: str = 'd'):
        """下载并保存单只股票数据"""
        try:
            # 获取需要补全的日期范围
            freq_str = 'daily' if frequency == 'd' else 'weekly'
            date_range = self.db.get_missing_dates(stock_code, freq_str)
            
            if date_range[0] > date_range[1]:
                return True, "数据已是最新"
            
            # 下载数据
            df, msg = self.download_stock_data(stock_code, frequency, date_range[0], date_range[1])
            
            if df is not None:
                self.db.insert_price_data(df, freq_str)
                return True, f"成功更新 {len(df)} 条数据"
            else:
                return False, msg
                
        except Exception as e:
            return False, f"异常: {str(e)}"
    
    def incremental_update(self, frequency: str = 'd', max_workers: int = 6, stock_list=None, debug_mode=False):
        """增量更新所有股票数据 - 使用高效并行下载（类似 bao_get_single_stock.py）"""
        freq_name = '日' if frequency == 'd' else '周'
        freq_flag = frequency  # 'd' 或 'w'
        
        print(f"🚀 开始高效并行增量更新{freq_name}线数据...")
        
        if debug_mode:
            from datetime import datetime
            now = datetime.now()
            print(f"🔍 调试模式开启")
            print(f"⏰ 当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"📅 星期: {['周一', '周二', '周三', '周四', '周五', '周六', '周日'][now.weekday()]}")
            last_trading_day = self.db._get_last_trading_day()
            print(f"📊 最后一个交易日: {last_trading_day}")
            print("-" * 60)
        
        # 获取所有股票代码
        if stock_list is None:
            stock_list = self.get_stock_list()
        if stock_list is not None and not stock_list.empty:
            if "code" in stock_list.columns:
                stock_list = stock_list[stock_list["code"].astype(str).str.startswith(("sh.", "sz."))]
                stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sz.30")]
                stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sh.688")]
                stock_list = stock_list[~stock_list["code"].astype(str).str.startswith("sh.689")]
            if "code_name" in stock_list.columns:
                stock_list = stock_list[~stock_list["code_name"].astype(str).str.contains("ST", na=False)]
        stock_codes = stock_list['code'].tolist()
        
        if debug_mode:
            print(f"📊 共 {len(stock_codes)} 只股票需要检查")
        
        # 批量获取所有股票的缺失日期范围，减少数据库查询次数
        update_tasks = []
        no_update_stocks = []
        
        for code in stock_codes:
            freq_str = 'daily' if frequency == 'd' else 'weekly'
            date_range = self.db.get_missing_dates(code, freq_str)
            
            if debug_mode:
                max_date = self.db.get_max_date(code, freq_str)
                print(f"\n📈 股票 {code} - {freq_name}线:")
                print(f"   数据库最新日期: {max_date or '无数据'}")
                print(f"   缺失日期范围: {date_range[0]} 到 {date_range[1]}")
                
                if max_date:
                    from datetime import datetime
                    max_date_dt = datetime.strptime(max_date, '%Y-%m-%d').date()
                    last_trading_day = self.db._get_last_trading_day()
                    
                    if max_date_dt >= last_trading_day:
                        print(f"   ✅ 数据已是最新 (数据库: {max_date_dt} >= 交易日: {last_trading_day})")
                    else:
                        print(f"   🔄 需要更新 (数据库: {max_date_dt} < 交易日: {last_trading_day})")
                        
                        # 对于周线，额外检查是否距离上一个周线日期超过一周
                        if freq_str == 'weekly':
                            days_since_last_update = (last_trading_day - max_date_dt).days
                            if days_since_last_update < 7:
                                print(f"   ⚠️  周线数据: 距离上次更新仅 {days_since_last_update} 天，无需更新")
                                no_update_stocks.append(code)
                                continue
                            else:
                                print(f"   🎯 周线数据: 距离上次更新 {days_since_last_update} 天，需要更新")
            
            if date_range[0] <= date_range[1] and date_range[0] != date_range[1]:
                update_tasks.append((code, date_range[0], date_range[1]))
                if debug_mode:
                    print(f"   🎯 需要更新: {date_range[0]} 到 {date_range[1]}")
            else:
                no_update_stocks.append(code)
                if debug_mode:
                    print(f"   ✅ 无需更新")
            
            if debug_mode:
                print("   " + "-" * 40)
        
        if debug_mode and no_update_stocks:
            print(f"📋 无需更新的股票: {len(no_update_stocks)} 只")
        
        print(f"🔧 需要更新 {len(update_tasks)} 只股票的数据")
        
        # 显示前10只需要更新的股票作为示例
        if len(update_tasks) > 0:
            print(f"📝 需要更新的股票示例 (前{min(10, len(update_tasks))}只):")
            for i, (code, start_date, end_date) in enumerate(update_tasks[:10]):
                print(f"   {i+1}. {code} - {start_date} 到 {end_date}")
        
        if len(update_tasks) == 0:
            print(f"✅ 所有{freq_name}线数据已是最新，无需更新")
            return True, 0, "所有数据已是最新，无需更新"
        
        success_count = 0
        fail_count = 0
        total_data_count = 0
        
        # 使用进程池并行下载，每个进程独立登录
        with ProcessPoolExecutor(
            max_workers=max_workers,
            initializer=self._init_worker,
            mp_context=mp.get_context("spawn"),
        ) as executor:
            # 提交所有下载任务
            futures = {}
            for code, start_date, end_date in update_tasks:
                future = executor.submit(self._download_and_process_stock_optimized, code, freq_flag, start_date, end_date)
                futures[future] = code
            
            with tqdm(total=len(futures), desc=f"{freq_name}线并行下载", unit="股") as pbar:
                for future in as_completed(futures):
                    code = futures[future]
                    try:
                        # 添加超时机制，防止单个股票下载卡住
                        success, data_count, msg = future.result(timeout=30)  # 30秒超时
                        if success:
                            success_count += 1
                            total_data_count += data_count
                        else:
                            fail_count += 1
                            if "无数据" not in msg and "已是最新" not in msg:
                                pbar.write(f"❌ [{code}] {msg}")
                    except TimeoutError:
                        fail_count += 1
                        pbar.write(f"⏰ [{code}] 下载超时 (30秒)，已跳过")
                    except Exception as e:
                        fail_count += 1
                        pbar.write(f"❌ [{code}] 任务异常: {e}")
                    
                    # 更新进度条显示
                    pbar.set_postfix({
                        '成功': success_count, 
                        '失败': fail_count,
                        '数据': total_data_count
                    })
                    pbar.update(1)
        
        print(f"✅ {freq_name}线更新完成: 成功 {success_count}, 失败 {fail_count}, 新增数据 {total_data_count} 条")
        
        # 返回更新结果
        if success_count > 0:
            return True, total_data_count, f"成功更新 {success_count} 只股票，新增 {total_data_count} 条数据"
        else:
            return False, 0, f"更新失败: {fail_count} 只股票更新失败"
    
    def _init_worker(self):
        """每个工作进程启动时调用，负责登录 baostock"""
        # 静默登录，避免重复输出
        bs.login()
        return
    
    def _download_and_process_stock_optimized(self, stock_code, frequency, start_date, end_date):
        """优化版的单个股票下载和处理（用于并行执行）"""
        try:
            # 更短的随机延迟，提高并发效率
            time.sleep(random.uniform(0.1, 0.3))
            
            timeout_seconds = 90
            if os.name == "posix":
                def _timeout_handler(signum, frame):
                    raise TimeoutError(f"任务超时({timeout_seconds}s)")

                old_handler = signal.signal(signal.SIGALRM, _timeout_handler)
                signal.alarm(timeout_seconds)
            else:
                old_handler = None

            try:
                df, msg = self.download_stock_data(stock_code, frequency, start_date, end_date)
            finally:
                if os.name == "posix":
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            
            if df is None:
                return False, 0, msg
            
            if len(df) == 0:
                return True, 0, "无新数据"
            
            # 插入数据库
            freq_str = 'daily' if frequency == 'd' else 'weekly'
            self.db.insert_price_data(df, freq_str, show_progress=False)
            
            return True, len(df), f"成功更新 {len(df)} 条数据"
            
        except Exception as e:
            return False, 0, f"处理异常: {str(e)}"

def main():
    downloader = BaoStockDownloader()
    
    try:
        downloader.login()
        
        # 1. 更新股票基本信息
        downloader.update_stock_info()
        
        # 2. 增量更新日线数据
        downloader.incremental_update('d', max_workers=4)
        
        # 3. 增量更新周线数据
        downloader.incremental_update('w', max_workers=4)
        
    except Exception as e:
        print(f"程序执行出错: {e}")
    finally:
        downloader.logout()

if __name__ == "__main__":
    main()
