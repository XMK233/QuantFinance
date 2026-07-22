# GPU加速回测系统使用指南

## 概述

本系统提供了GPU加速的策略回测功能，通过并行化和GPU计算大幅提高回测计算速度。系统支持两种GPU加速库：CuPy和PyTorch。

## 系统要求

### 硬件要求
- NVIDIA GPU（推荐RTX 4070 Ti Super或更高）
- 16GB以上显存
- 32GB以上系统内存

### 软件要求
- Python 3.8+
- 以下任一GPU加速库：
  - CuPy（推荐）
  - PyTorch（备选）

## 安装GPU加速库

### 安装CuPy（推荐）
```bash
pip install cupy-cuda12x  # 根据你的CUDA版本选择
```

### 安装PyTorch（备选）
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

## 使用方法

### 1. 使用GPU加速回测

#### 方法一：使用`run_backtest.py`的GPU选项
```bash
# 启用GPU加速
python run_backtest.py full \
  --start-date 2025-01-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir full_backtest_2025_gpu \
  --gpu \
  --workers 4
```

#### 方法二：直接使用`accelerated_backtest.py`
```bash
python accelerated_backtest.py \
  --start-date 2025-01-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir accelerated_results \
  --workers 4
```

### 2. 使用原始回测系统（无GPU加速）
```bash
python run_backtest.py full \
  --start-date 2025-01-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir full_backtest_2025
```

## 命令行参数

### 通用参数
- `--start-date`: 回测开始日期（默认：2025-01-01）
- `--initial-capital`: 初始资金（默认：50000）
- `--max-positions`: 最大持仓数量（默认：3）
- `--max-price`: 最高买入价格（默认：150.0）
- `--output-dir`: 输出目录

### GPU加速参数
- `--gpu`: 启用GPU加速（如果可用）
- `--no-gpu`: 禁用GPU加速
- `--workers`: 工作进程数量（默认：CPU核心数-1）

## 性能测试

### 运行性能比较测试
```bash
# 测试GPU可用性
python performance_test.py --test-gpu

# 运行性能比较（每种配置运行3次）
python performance_test.py --runs 3

# 跳过可视化图表
python performance_test.py --runs 2 --skip-visualization
```

### 测试脚本
```bash
# 测试基本功能
python simple_test.py

# 测试完整功能
python test_accelerated_system.py
```

## 加速效果

### 预期加速比
| 配置 | 预期加速比 | 说明 |
|------|------------|------|
| 原始系统 | 1.0x | 基准 |
| CPU并行（4进程） | 2.5-3.5x | 多进程并行计算 |
| GPU加速（CuPy） | 5-10x | GPU并行计算 |
| GPU加速（PyTorch） | 4-8x | GPU计算，略有开销 |

### 实际测试结果
运行以下命令查看实际加速效果：
```bash
python performance_test.py --runs 3
```

## 技术实现

### GPU加速原理
1. **批量计算**: 将多个股票的计算任务批量处理
2. **并行处理**: 使用多进程并行获取数据
3. **GPU计算**: 使用CuPy或PyTorch进行矩阵运算

### 关键优化点
1. **数据预取**: 批量获取股票数据，减少I/O次数
2. **并行策略推荐**: 并行计算策略信号
3. **GPU得分计算**: 使用GPU加速股票得分计算
4. **批量收益率计算**: 批量计算持仓收益率

## 故障排除

### 常见问题

#### 1. GPU检测失败
**症状**: 系统显示"GPU加速不可用"
**解决方案**:
```bash
# 检查GPU驱动
nvidia-smi

# 安装正确的CUDA版本
pip install cupy-cuda12x  # 根据你的CUDA版本
```

#### 2. 内存不足
**症状**: 程序崩溃或报内存错误
**解决方案**:
- 减少`--workers`数量
- 使用`--no-gpu`禁用GPU加速
- 减少回测期间

#### 3. Pickle错误
**症状**: "Can't pickle local object"错误
**解决方案**:
- 系统已修复此问题
- 如果仍出现，请使用简化版本

### 调试模式
```bash
# 启用详细日志
python accelerated_backtest.py --gpu --workers 2 2>&1 | tee debug.log
```

## 示例

### 完整回测示例
```bash
# GPU加速回测（2025年全年）
python run_backtest.py full \
  --start-date 2025-01-01 \
  --end-date 2025-12-31 \
  --initial-capital 100000 \
  --max-positions 5 \
  --max-price 200.0 \
  --output-dir backtest_2025_full \
  --gpu \
  --workers 8
```

### 快速测试示例
```bash
# 快速测试（最近30天）
python run_backtest.py full \
  --start-date 2026-05-01 \
  --initial-capital 50000 \
  --max-positions 3 \
  --max-price 150.0 \
  --output-dir quick_test \
  --gpu
```

## 注意事项

1. **首次运行**: GPU加速库首次加载需要时间
2. **显存使用**: 大回测期间可能消耗大量显存
3. **数据获取**: 网络延迟可能影响整体性能
4. **结果验证**: 建议对比GPU和CPU版本的结果

## 性能优化建议

1. **批量大小**: 适当调整批量大小（默认100）
2. **工作进程**: 根据CPU核心数设置工作进程
3. **数据缓存**: 系统自动缓存常用数据
4. **网络优化**: 确保稳定的网络连接

## 支持与反馈

如有问题或建议，请：
1. 检查系统日志
2. 运行测试脚本验证功能
3. 提供详细的错误信息

## 更新日志

### v1.0 (2026-06-18)
- 初始版本发布
- 支持CuPy和PyTorch GPU加速
- 实现并行策略推荐
- 添加性能测试工具

---

**注意**: 本系统为高性能计算设计，建议在具备足够硬件资源的机器上运行。对于大规模回测，建议分阶段进行并监控系统资源使用情况。