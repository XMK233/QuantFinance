# 策略目录（Strategy Catalog）

用于记录 `daily_trading_system.py` 里可用的 `--strategy` 策略名、含义与使用方式，便于快速查阅与组合。

## 策略列表

| 策略名 (`--strategy`) | 中文解释 | 业务意义 | 关键参数 |
|---|---|---|---|
| `multi_factor` | 多因子综合策略（现有 `TradingStrategy` 评分） | 融合周线趋势/突破/回调等多个信号，输出置信度并排序 | 无 |
| `cross_ma50` | 一阳穿四线策略（近 4 周一阳穿四线 + 非 ST + 收盘价 < 价格上限） | 用强趋势 K 线形态筛选强势启动票，同时限制高价票便于资金分配 | `--price-cap`（默认 50） |
| `weekly_mean_down` | 周均价下移策略（近 0~30 周均价 < 近 30~60 周均价） | 筛选周线均值回落的标的，常用于“回撤后再选择/均值回归”类探索 | 无 |
| `weekly_reg_down_10w` | 周回归下行策略（近 10 周收盘价线性回归后整体呈下降趋势） | 用“回归斜率<0 且拟合度达标”刻画近 10 周的系统性下行（适合做反转/超跌类候选池的前置筛选） | 无 |
| `bottom_doji` | 底部十字星策略（先满足 `weekly_reg_down_10w`，再满足近 2 周出现底部十字星） | 在下行趋势末端寻找“抛压减弱/犹豫”信号，用于反转或止跌观察的候选池 | 无 |

## 使用示例

单策略（多因子综合）：

```bash
python daily_trading_system.py --skip-update --recommend-only --strategy multi_factor
```

链式策略（按顺序依次筛选，最终取 3 只票输出建议操作）：

```bash
python daily_trading_system.py --skip-update --recommend-only --strategy cross_ma50 weekly_mean_down --ignore-holdings --price-cap 50
```
