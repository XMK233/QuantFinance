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

### 4. 每日交易系统（使用已有数据跳过更新）
```bash
# 跳过数据更新步骤，直接基于现有数据库数据生成持仓监控、卖出建议、买入推荐等后续流程
python daily_trading_system.py --skip-update
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

## 因子列表（stock_operators）

策略在 [trading_strategy.py](file:///mnt/d/forCoding_code/QuantFinance/plan_3-standardization_1/trading_strategy.py) 中通过各算子类的 `calculate()` 计算因子，并把返回的字段合并为因子字典。

| 算子函数名 | 因子字段 | 中文含义 | 备注 |
|---|---|---|---|
| `CrossMAOperator.calculate` | `cross_ma_2w` | 过去2周内是否出现“一阳穿四线”（周线） |  |
| `CrossMAOperator.calculate` | `cross_ma_4w` | 过去4周内是否出现“一阳穿四线”（周线） |  |
| `CrossMAOperator.calculate` | `cross_ma_8w` | 过去8周内是否出现“一阳穿四线”（周线） |  |
| `STStockOperator.calculate` | `is_st` | 是否 ST / 风险警示 / 退市等特殊标记 |  |
| `LimitUpOperator.calculate` | `has_limit_up` | 近一周（日线5个交易日）是否出现涨停 |  |
| `LimitUpOperator.calculate` | `has_limit_up_pullback` | 近一周是否出现“涨停后回调”形态 |  |
| `VolumeBreakOperator.calculate` | `volume_break_count` | 75周内“放量突破20周线”的次数 |  |
| `VolumeBreakOperator.calculate` | `volume_break_ge_2` | 放量突破次数是否≥2 |  |
| `MADivergenceOperator.calculate` | `ma_divergence` | 5/10/20周均线是否多头排列且走强（发散走多） |  |
| `BreakthroughPullbackOperator.calculate` | `breakthrough_pullback` | 最近一次突破20周线后，是否出现缩量回调且不跌破突破周收盘价 |  |
| `ListingDateOperator.calculate` | `listing_days` | 上市天数 |  |
| `ListingDateOperator.calculate` | `listing_gt_240` | 上市是否超过240天 |  |
| `WeeklyBreakoutOperator.calculate` | `weekly_breakout_20w` | 是否突破近20周新高且收盘在MA20上方 |  |
| `WeeklyBreakoutOperator.calculate` | `weekly_breakout_20w_volume` | 是否突破近20周新高且放量（成交量>20周均量*1.2） |  |
| `PullbackMA20ReboundOperator.calculate` | `pullback_ma20_rebound` | 近几日是否回踩日线MA20附近并出现反弹确认 |  |
| `WeeklyMASlopeOperator.calculate` | `weekly_ma20_slope` | 周线MA20最近斜率（近两周变化率） |  |
| `WeeklyMASlopeOperator.calculate` | `weekly_ma20_up_3w` | 周线MA20是否连续3周上行 |  |
| `DailyBBSqueezeOperator.calculate` | `bb_width` | 布林带宽度（(上轨-下轨)/MA20） | 慢因子（需 `--enable-slow-factors`） |
| `DailyBBSqueezeOperator.calculate` | `bb_squeeze` | 是否布林带挤压（宽度接近近40日最低） | 慢因子（需 `--enable-slow-factors`） |
| `DailyBBSqueezeOperator.calculate` | `bb_breakout` | 是否向上突破布林上轨 | 慢因子（需 `--enable-slow-factors`） |
| `DailyBBSqueezeOperator.calculate` | `bb_squeeze_breakout` | 是否“挤压+突破+放量”组合信号 | 慢因子（需 `--enable-slow-factors`） |
| `DailyAR1ReturnOperator.calculate` | `ts_ar1_phi` | 日线对数收益AR(1)系数 φ | 慢因子（需 `--enable-slow-factors`） |
| `DailyAR1ReturnOperator.calculate` | `ts_ar1_pred_next` | AR(1)预测的下一期收益（对数收益） | 慢因子（需 `--enable-slow-factors`） |
| `DailyAR1ReturnOperator.calculate` | `ts_ar1_r2` | AR(1)拟合优度 R² | 慢因子（需 `--enable-slow-factors`） |
| `DailyAR1ReturnOperator.calculate` | `ts_ar1_momentum` | AR(1)动量信号（φ>0.1 且预测收益>0） | 慢因子（需 `--enable-slow-factors`） |
| `WeeklyAR1ReturnOperator.calculate` | `ts_w_ar1_phi` | 周线对数收益AR(1)系数 φ | 慢因子（需 `--enable-slow-factors`） |
| `WeeklyAR1ReturnOperator.calculate` | `ts_w_ar1_pred_next` | 周线AR(1)预测的下一期收益（对数收益） | 慢因子（需 `--enable-slow-factors`） |
| `WeeklyAR1ReturnOperator.calculate` | `ts_w_ar1_momentum` | 周线AR(1)动量信号（φ>0.1 且预测收益>0） | 慢因子（需 `--enable-slow-factors`） |
| `DailyHurstOperator.calculate` | `ts_hurst` | Hurst 指数（趋势性>0.5，均值回归<0.5） | 慢因子（需 `--enable-slow-factors`） |
| `DailyHurstOperator.calculate` | `ts_hurst_trend` | 是否偏趋势（H>0.55） | 慢因子（需 `--enable-slow-factors`） |
| `DailyHurstOperator.calculate` | `ts_hurst_mean_revert` | 是否偏均值回归（H<0.45） | 慢因子（需 `--enable-slow-factors`） |
| `DailyVolatilityRegimeOperator.calculate` | `ts_vol_ratio` | 波动率状态比值（快EWMA波动/慢EWMA波动） | 慢因子（需 `--enable-slow-factors`） |
| `DailyVolatilityRegimeOperator.calculate` | `ts_vol_high` | 是否高波动状态（ratio>1.3） | 慢因子（需 `--enable-slow-factors`） |
| `DailyVolatilityRegimeOperator.calculate` | `ts_vol_low` | 是否低波动状态（ratio<0.8） | 慢因子（需 `--enable-slow-factors`） |

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
