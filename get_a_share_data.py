import tushare as ts

# 设置 tushare token
token = '53b6254438e6d307b6799dbd575883528bc1da912f3d6a31159ecc9e'
ts.set_token(token)

# 初始化 pro 接口
pro = ts.pro_api()

try:
    # 尝试获取平安银行(000001.SZ)的日线数据
    df = pro.daily(ts_code='000001.SZ', start_date='20240101', end_date='20240131')
    
    print("成功获取数据：")
    print(df.head())
    
    # 备选：获取股票列表
    # data = pro.stock_basic(exchange='', list_status='L', fields='ts_code,symbol,name,area,industry,list_date')
    # print(data.head())

except Exception as e:
    print(f"获取数据失败: {e}")
