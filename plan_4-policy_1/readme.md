# 策略回测系统

基于 `weekly_mean_down` 和 `cross_ma50` 策略组合的回测系统，用于评估策略的长期有效性。

## 需求概述

从2025年第一个交易日开始，使用5万元初始资金，遵循以下规则：
- 最多持有3只沪深主板股票（排除创业板、科创板）
- 不买入单价高于150元的股票
- 使用 `weekly_mean_down` 和 `cross_ma50` 策略组合选股
- 自动执行止盈止损策略
- 输出每个交易日的持仓情况、盈利情况、总盈利情况

## 系统架构

```
plan_4-policy_1/
├── backtest_system.py      # 主回测系统
├── strategy_combiner.py    # 策略组合器
├── data_manager.py         # 数据管理器
├── results_exporter.py     # 结果导出器
├── run_backtest.py         # 主运行脚本
└── README.md              # 说明文档
```

## 依赖关系

- Python 3.8+
- pandas
- numpy
- matplotlib
- tqdm
- plan_3-standardization_1 中的策略代码

## 使用方法

### 1. 运行完整回测

```bash
# 使用默认参数
python run_backtest.py full

# 自定义参数
python run_backtest.py full \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir my_results
```

### 2. 运行快速测试

```bash
python run_backtest.py test
```

### 3. 分析策略表现

```bash
python run_backtest.py analyze
```

### 4. 直接使用回测系统

```bash
python backtest_system.py \
  --start-date 2025-01-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir backtest_results
```

## 核心功能

### 1. 策略组合 (`strategy_combiner.py`)
- 组合 `weekly_mean_down` 和 `cross_ma50` 策略
- 按顺序筛选：先应用 `cross_ma50`，再应用 `weekly_mean_down`
- 返回符合所有条件的股票推荐

### 2. 数据管理 (`data_manager.py`)
- 获取交易日历
- 查询股票价格历史
- 过滤ST股票
- 按价格范围过滤股票
- 保存价格数据

### 3. 回测引擎 (`backtest_system.py`)
- 模拟每日交易
- 持仓管理（买入、卖出）
- 止盈止损策略
- 手续费计算
- 每日状态记录

### 4. 结果导出 (`results_exporter.py`)
- 导出CSV格式的每日记录和交易历史
- 生成统计报告（文本和JSON格式）
- 绘制资金曲线图
- 绘制交易分析图
- 生成HTML综合报告

## 交易规则

### 买入条件
1. 股票必须同时满足 `weekly_mean_down` 和 `cross_ma50` 策略
2. 当前价格 ≤ 150元
3. 持仓数量 < 3只
4. 可用资金 ≥ 1000元
5. 买入股数为100股的整数倍

### 卖出条件（满足任一即卖出）
1. 止损：收益率 ≤ -8%
2. 止盈：收益率 ≥ 15%
3. 持有时间：≥ 60天

### 手续费
- 费率：0.791‱（万0.791）
- 最低手续费：5元

## 输出文件

回测完成后，会在输出目录生成以下文件：

```
backtest_results/
├── daily_records_YYYYMMDD_HHMMSS.csv      # 每日记录
├── trade_history_YYYYMMDD_HHMMSS.csv      # 交易历史
├── statistics_YYYYMMDD_HHMMSS.txt         # 统计报告（文本）
├── statistics_YYYYMMDD_HHMMSS.json        # 统计报告（JSON）
├── equity_curve_YYYYMMDD_HHMMSS.png       # 资金曲线图
├── trade_analysis_YYYYMMDD_HHMMSS.png     # 交易分析图
└── report_YYYYMMDD_HHMMSS.html           # HTML综合报告
```

## 统计指标

### 财务表现
- 初始资金、最终总资产
- 总收益、总收益率
- 年化收益率

### 交易质量
- 总交易次数、买入/卖出次数
- 胜率（盈利交易比例）
- 平均每笔盈利
- 最大盈利、最大亏损

### 风险指标
- 年化波动率
- 夏普比率

## 示例命令

### 完整回测（2025年至今）
```bash
python run_backtest.py full \
  --start-date 2025-01-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir full_backtest_2025
```

### 快速测试（最近60天）
```bash
python run_backtest.py test
```

### 策略分析
```bash
python run_backtest.py analyze
```

## 注意事项

1. **数据依赖**：系统依赖 `plan_3-standardization_1` 中的数据获取功能
2. **交易日历**：优先从股票数据中获取交易日历，失败时使用工作日历
3. **价格查询**：如果无法获取指定日期的价格，使用最近的前一个交易日价格
4. **内存使用**：处理大量股票数据时可能需要较多内存
5. **运行时间**：完整回测可能需要较长时间，具体取决于交易日数量

## 扩展性

系统设计为模块化，易于扩展：
- 添加新策略：在 `strategy_combiner.py` 中添加策略组合
- 修改交易规则：在 `backtest_system.py` 中调整参数
- 自定义输出：在 `results_exporter.py` 中添加新的导出格式

## 故障排除

### 常见问题
1. **导入错误**：确保 `plan_3-standardization_1` 目录在Python路径中
2. **数据缺失**：检查网络连接和数据文件完整性
3. **内存不足**：减少回测期间或股票数量
4. **运行缓慢**：使用快速测试模式或减少交易日数量

### 调试模式
```bash
# 设置日志级别
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 版本历史

- v1.0 (2025-06-18): 初始版本，实现基本回测功能
- 包含完整的策略组合、数据管理、回测引擎和结果导出

## 许可证

本项目基于现有代码库开发，遵循原有许可证。