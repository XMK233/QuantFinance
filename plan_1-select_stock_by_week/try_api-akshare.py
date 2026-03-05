
import akshare as ak
import pandas as pd
import os
import time
from tqdm import tqdm
from requests.exceptions import RequestException
from http.client import RemoteDisconnected

ORIGINAL_DATA_DIR = '/mnt/d/forCoding_data/QuantFinance/plan_1-select_stock_by_week/originalData/'

## 下载A股沪深两市所有的核准股票的周度数据到 ORIGINAL_DATA_DIR 目录中存储。我后续需要做分析。

# import akshare as ak
# stock_code = "600519"
# df = ak.stock_zh_a_hist(symbol=stock_code, period="daily")
# df = df.rename(columns={
#     '日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low',
#     '成交量': 'volume', '成交额': 'amount', '涨跌幅': 'pct_chg', '换手率': 'turnover_rate'
# })

def get_all_stocks(max_retries=5):
    """获取所有A股股票列表，增加重试机制和备选接口"""
    for attempt in range(max_retries):
        try:
            print(f"尝试获取股票列表 (第 {attempt + 1} 次)...")
            # 优先尝试 ak.stock_zh_a_spot_em() 获取实时行情数据，包含所有A股代码
            # 注意：这里获取的是实时行情，包含了所有在交易的股票
            df = ak.stock_zh_a_spot_em()
            if not df.empty:
                return df
        except (ConnectionError, RemoteDisconnected, RequestException, Exception) as e:
            print(f"尝试1 (stock_zh_a_spot_em) 失败: {e}")
            
            # 尝试备选接口：ak.stock_info_a_code_name()
            try:
                print("尝试备选接口 (stock_info_a_code_name)...")
                df = ak.stock_info_a_code_name()
                # 统一列名以匹配后续逻辑
                if not df.empty and 'code' in df.columns:
                     df = df.rename(columns={'code': '代码', 'name': '名称'})
                     return df
            except Exception as e2:
                print(f"备选接口也失败: {e2}")

            if attempt < max_retries - 1:
                wait_time = 3 * (attempt + 1)
                print(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
            else:
                print("获取股票列表最终失败。")
                
    return pd.DataFrame()

def download_stock_data(symbol, period='weekly', max_retries=5):
    """下载单个股票数据，带有重试机制"""
    for attempt in range(max_retries):
        try:
            # 获取历史行情数据
            # adjust='qfq' 前复权，适合做分析
            df = ak.stock_zh_a_hist(symbol=symbol, period=period, adjust="qfq")
            
            if df.empty:
                return None
            
            # 重命名列，保持与参考代码一致
            # 注意：akshare返回的列名可能随版本更新变化，这里使用参考代码中的映射
            # 如果是周线数据，列名通常也是中文，需要确保映射正确
            rename_dict = {
                '日期': 'date', '开盘': 'open', '收盘': 'close', '最高': 'high', '最低': 'low',
                '成交量': 'volume', '成交额': 'amount', '涨跌幅': 'pct_chg', '换手率': 'turnover_rate'
            }
            # 仅重命名存在的列
            df = df.rename(columns=rename_dict)
            
            return df
            
        except (ConnectionError, RemoteDisconnected, RequestException, Exception) as e:
            if attempt < max_retries - 1:
                # 指数退避策略
                wait_time = 2 * (attempt + 1)
                # print(f"下载 {symbol} 失败，{wait_time}秒后重试 ({attempt + 1}/{max_retries})... 错误: {e}")
                time.sleep(wait_time)
                continue
            else:
                print(f"下载 {symbol} 失败，已达到最大重试次数。错误: {e}")
                return None

def main():
    # 确保存储目录存在
    if not os.path.exists(ORIGINAL_DATA_DIR):
        try:
            os.makedirs(ORIGINAL_DATA_DIR)
            print(f"已创建目录: {ORIGINAL_DATA_DIR}")
        except OSError as e:
            print(f"创建目录失败: {e}")
            return

    print("正在获取A股股票列表...")
    stocks_df = get_all_stocks()
    
    if stocks_df.empty:
        print("未能获取股票列表，程序退出。")
        return

    # 提取股票代码列表
    # ak.stock_zh_a_spot_em 返回的 DataFrame 中，股票代码列名为 '代码'
    if '代码' not in stocks_df.columns:
        print("股票列表数据格式不符合预期（缺少'代码'列），程序退出。")
        print("列名:", stocks_df.columns)
        return

    stocks_list = stocks_df['代码'].tolist()
    total_stocks = len(stocks_list)
    
    print(f"共获取到 {total_stocks} 只股票。")
    print("开始下载周度数据 (Weekly Data)...")
    
    # 使用 tqdm 显示进度条
    # unit='stock' 设置进度条单位
    success_count = 0
    fail_count = 0
    
    pbar = tqdm(stocks_list, total=total_stocks, unit='stock', desc="Downloading")
    
    for symbol in pbar:
        file_path = os.path.join(ORIGINAL_DATA_DIR, f"{symbol}.csv")
        
        # 可选：如果文件已存在且近期已更新，可以跳过
        # 这里默认覆盖更新，保证数据最新
        
        df = download_stock_data(symbol, period='weekly')
        
        if df is not None and not df.empty:
            try:
                df.to_csv(file_path, index=False)
                success_count += 1
            except Exception as e:
                print(f"保存 {symbol} 数据失败: {e}")
                fail_count += 1
        else:
            fail_count += 1
            
        # 更新进度条后缀信息
        pbar.set_postfix({'Success': success_count, 'Fail': fail_count})
        
        # 稍微延时，避免请求过于频繁被封IP
        # time.sleep(0.05)

    print("\n下载完成！")
    print(f"成功: {success_count}, 失败: {fail_count}")
    print(f"数据已保存至: {ORIGINAL_DATA_DIR}")

if __name__ == "__main__":
    main()
