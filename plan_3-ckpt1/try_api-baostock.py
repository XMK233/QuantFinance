import baostock as bs
import pandas as pd
import time
import os

def fetch_and_save_stock_list():
    """
    获取沪深A股所有股票列表并保存到本地CSV文件
    """
    
    # 1. 登录系统
    # 也可以使用自己的用户名和密码，这里使用默认用户
    lg = bs.login()
    
    # 检查登录是否成功
    if lg.error_code != '0':
        print(f"登录失败: {lg.error_msg}")
        return

    print('系统登录成功: ' + lg.error_msg)

    try:
        # 2. 获取证券基本资料
        # query_stock_basic 返回所有股票的基本信息
        # 我们可以通过 code="" 来获取所有，或者指定 specific code
        # 为了避免数据量过大导致超时或被限制，通常获取列表是安全的
        print("开始获取股票列表...")
        
        rs = bs.query_stock_basic()
        
        if rs.error_code != '0':
            print(f"获取股票列表失败: {rs.error_msg}")
            return

        # 3. 解析结果集
        data_list = []
        while (rs.error_code == '0') & rs.next():
            # 获取一条记录，将记录合并在一起
            # 每一行数据包含：code, tradeStatus, code_name 等
            # 我们可以过滤掉退市的股票，如果需要只保留在市的
            # status: 1:上市, 0:退市, 2:暂停上市
            # type: 1:股票，2:指数，3:其它
            
            row_data = rs.get_row_data()
            data_list.append(row_data)
        
        # 4. 转换为 DataFrame
        result = pd.DataFrame(data_list, columns=rs.fields)
        
        # 筛选条件：保留上市状态 (status=1) 且 类型为股票 (type=1) 的记录
        # 注意：baostock 返回的数据全是字符串类型，需要注意比较
        # 具体的字段定义请参考 baostock 官方文档，这里为了保险起见，先保存所有原始数据
        # 或者我们可以简单过滤一下 status='1' (上市)
        
        # result = result[result['status'] == '1'] 
        
        # 5. 保存结果到本地
        # 获取当前脚本所在目录
        current_dir = os.path.dirname(os.path.abspath(__file__))
        output_file = os.path.join(current_dir, "all_stock_list.csv")
        
        result.to_csv(output_file, encoding="utf-8", index=False)
        print(f"成功获取 {len(result)} 条股票记录")
        print(f"文件已保存至: {output_file}")
        
        # 简单防封策略：避免短时间内频繁请求
        # 如果这是在循环中调用，建议添加 time.sleep(1)
        # 单次运行通常没有问题
        
    except Exception as e:
        print(f"发生异常: {e}")
        
    finally:
        # 6. 登出系统
        bs.logout()
        print('系统已登出')

if __name__ == '__main__':
    # 注意：请确保已安装 baostock 和 pandas
    # pip install baostock pandas
    
    fetch_and_save_stock_list()
