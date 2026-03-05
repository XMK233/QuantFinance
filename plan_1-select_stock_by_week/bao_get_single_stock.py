
## 加载all_stock_list.csv，获取 code 列的股票代码。
## 然后，下载每个代码的周k线数据，保存到以股票代码命名的csv文件中。
## 先下载5个股票的试试。
## 注意请求数据的时候不要太频繁，避免被服务器拒绝。每获得一个股票的数据就随机休息0～3秒。

import baostock as bs
import pandas as pd
import os
import time
import random
import datetime
import tqdm
from concurrent.futures import ProcessPoolExecutor, as_completed

# 常量定义
DATA_DIR = '/mnt/d/forCoding_data/QuantFinance/plan_1-select_stock_by_week/originalData/'
STOCK_LIST_FILE = '/mnt/d/forCoding_code/QuantFinance/plan_1-select_stock_by_week/all_stock_list.csv'
MAX_WORKERS = 6  # 进程数，控制并发度以避免封IP
START_DATE = "2023-01-01"

def init_worker():
    """每个工作进程启动时调用，负责登录 baostock"""
    bs.login()

def download_one_stock(code):
    """下载单个股票数据的函数，运行在子进程中"""
    try:
        # 获取当前日期作为结束日期 (放在这里是为了保证日期是最新的)
        end_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # 随机休眠，避免并发请求过于密集
        # 并发情况下，单线程休眠时间可以适当缩短，因为整体请求频率由 进程数 * (1/平均耗时) 决定
        time.sleep(random.uniform(0.1, 1.5))
        
        rs = bs.query_history_k_data_plus(
            code,
            "date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg",
            start_date=START_DATE, 
            end_date=end_date,
            frequency="w", 
            adjustflag="2"
        )

        if rs.error_code != '0':
            return False, f"下载失败: {rs.error_msg}"

        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        
        if not data_list:
            return True, "无数据" # 视为成功处理，只是没数据
        
        result = pd.DataFrame(data_list, columns=rs.fields)
        
        # 保存到 CSV
        file_path = os.path.join(DATA_DIR, f"{code}.csv")
        result.to_csv(file_path, index=False)
        
        return True, "成功"

    except Exception as e:
        return False, f"异常: {str(e)}"

def main():
    # 1. 创建保存数据的目录
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"创建目录: {DATA_DIR}")

    # 2. 加载股票列表
    if not os.path.exists(STOCK_LIST_FILE):
        print(f"错误: 找不到股票列表文件 {STOCK_LIST_FILE}")
        return

    print(f"正在读取股票列表: {STOCK_LIST_FILE}")
    stock_list_df = pd.read_csv(STOCK_LIST_FILE)
    
    # 简单过滤：只取 type=1 (股票)
    if 'type' in stock_list_df.columns:
        stock_list_df = stock_list_df[stock_list_df['type'] == 1]
    
    codes = stock_list_df['code'].tolist()
    
    # 可以在这里切片进行测试，例如 codes = codes[:20]
    target_codes = codes
    print(f"计划下载 {len(target_codes)} 只股票的数据，使用 {MAX_WORKERS} 个进程并发")

    # 3. 使用进程池并发下载
    # 注意：baostock 的 login 需要在每个进程中独立进行，或者使用 initializer
    with ProcessPoolExecutor(max_workers=MAX_WORKERS, initializer=init_worker) as executor:
        # 提交所有任务
        future_to_code = {executor.submit(download_one_stock, code): code for code in target_codes}
        
        # 使用 tqdm 显示进度
        pbar = tqdm.tqdm(total=len(target_codes), desc="下载进度")
        
        for future in as_completed(future_to_code):
            code = future_to_code[future]
            try:
                success, msg = future.result()
                if not success:
                    # 仅在失败时打印详细信息，避免刷屏
                    pbar.write(f"[{code}] {msg}")
            except Exception as e:
                pbar.write(f"[{code}] 任务执行异常: {e}")
            
            pbar.update(1)
            
        pbar.close()

    print("所有任务完成。")
    print("已登出 baostock")

if __name__ == "__main__":
    main()
