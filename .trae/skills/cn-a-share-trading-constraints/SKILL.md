---
name: "cn-a-share-trading-constraints"
description: "Encodes A-share trading constraints (capital, max holdings, boards, fees). Invoke when giving buy/sell operation advice in this repo."
---

# A股交易约束（必须前置考虑）

在本仓库里，只要输出任何“操作建议”（买入/卖出/止盈/止损/仓位/资金分配），都必须把以下约束作为前提：

- 综合给出买入和卖出的建议（同一轮输出里同时考虑持仓与候选标的）。
- 起始资金总量：50000 人民币。
- 持仓数量：手头持有不超过 3 支（阈值应当可调整）。
- 标的范围：只做上证/深证普通 A 股；过滤掉科创板、创业板、ST 等特殊票。
- 因子算子位置：/mnt/d/forCoding_code/QuantFinance/plan_3-standardization_1/stock_operators
- 交易费率：万分之 0.791；单笔不足 5 元按 5 元计。

## 输出建议时的默认处理原则

- 若持仓已满（达到上限），优先输出卖出/止盈建议；买入建议只在有空位时给出。
- 买入建议数量不超过可用空位数量。
- 买入资金分配应与最大持仓数一致（例如等权分配），并在计算买入股数时计入手续费。
