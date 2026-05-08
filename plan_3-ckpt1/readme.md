# 股票数据增量更新系统

基于 baostock API 和 SQLite 数据库的股票数据自动化更新系统。

## 功能特性

- ✅ **自动增量更新**: 每周五收盘后自动获取最新数据
- ✅ **智能补全**: 自动检测缺失日期，只下载需要的数据
- ✅ **并发下载**: 多进程并发提高下载效率
- ✅ **数据持久化**: SQLite 数据库存储，便于查询分析
- ✅ **错误处理**: 完善的异常处理和重试机制

## 文件说明

- `stock_database.py` - SQLite 数据库操作类
- `bao_data_downloader.py` - baostock 数据下载核心逻辑
- `run_weekly_update.py` - 主运行脚本
- `try_api-baostock.py` - 原始股票列表获取代码
- `bao_get_single_stock.py` - 原始单股票下载代码

## 安装依赖

```bash
pip install baostock pandas tqdm sqlite3
```

## 使用方法

### 1. 首次运行（获取历史数据）
```bash
python run_weekly_update.py
```

### 2. 每周五收盘后运行（增量更新）
```bash
python run_weekly_update.py
```

### 3. 测试模式（只处理少量股票）
```bash
python run_weekly_update.py --test
```

## 数据库结构

### stocks 表（股票基本信息）
- `code`: 股票代码
- `name`: 股票名称
- `industry`: 所属行业
- `market`: 市场（SH/SZ）
- `listing_date`: 上市日期

### stock_daily 表（日线数据）
- `stock_code`: 股票代码
- `date`: 交易日期
- `open/high/low/close`: OHLC 价格
- `volume/amount`: 成交量/成交额
- `turnover_rate`: 换手率
- `pe_ratio/pb_ratio`: 市盈率/市净率

### stock_weekly 表（周线数据）
- 同日线数据结构

## 增量更新逻辑

1. **检测最新日期**: 查询数据库中每只股票的最新日期
2. **计算缺失范围**: 从最新日期的下一天开始到当前日期
3. **只下载缺失数据**: 避免重复下载已有数据
4. **智能插入**: 使用 `INSERT OR REPLACE` 避免重复数据

## 自动化部署

可以将 `run_weekly_update.py` 添加到 crontab 中，每周五收盘后自动运行：

```bash
# 每周五 15:30 运行
30 15 * * 5 cd /path/to/your/project && python run_weekly_update.py
```

## 注意事项

1. 请确保网络连接正常
2. baostock API 有请求频率限制，建议控制并发数
3. 首次运行需要下载全部历史数据，时间较长
4. 建议定期备份数据库文件