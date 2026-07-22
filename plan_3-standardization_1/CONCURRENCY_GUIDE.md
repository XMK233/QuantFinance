# 并发模式使用指南

## 问题背景
baostock 对多进程并发访问有限制，当使用多进程模式时可能会遇到访问失败或限制问题。

## 解决方案
我们为数据下载器添加了三种并发模式，可以根据需要选择：

### 1. 单线程模式 (`--mode single`)
- **特点**: 最稳定，避免所有并发问题
- **适用场景**: baostock 访问限制严重时
- **命令示例**:
  ```bash
  python bao_data_downloader.py --mode single --workers 1
  python daily_update.py --mode single --workers 1
  python run_weekly_update.py --mode single --workers 1
  ```

### 2. 多线程模式 (`--mode thread`)
- **特点**: 在避免baostock限制的同时提供一定并发性
- **适用场景**: 需要一定并发性但避免多进程限制
- **命令示例**:
  ```bash
  python bao_data_downloader.py --mode thread --workers 4
  python daily_update.py --mode thread --workers 4
  python run_weekly_update.py --mode thread --workers 4
  ```

### 3. 多进程模式 (`--mode process`)
- **特点**: 速度最快，但可能触发baostock限制
- **适用场景**: 网络环境良好，baostock限制不严格时
- **命令示例**:
  ```bash
  python bao_data_downloader.py --mode process --workers 6
  python daily_update.py --mode process --workers 6
  python run_weekly_update.py --mode process --workers 6
  ```

## 各脚本参数说明

### bao_data_downloader.py
```bash
python bao_data_downloader.py --mode single --workers 1 --skip-weekly --debug
```
- `--mode`: 并发模式 (single/thread/process)
- `--workers`: 工作进程/线程数
- `--skip-daily`: 跳过日线数据更新
- `--skip-weekly`: 跳过周线数据更新
- `--debug`: 启用调试模式
- `--force-update`: 强制更新股票基本信息

### daily_update.py
```bash
python daily_update.py --mode thread --workers 3 --full
```
- `--mode`: 并发模式 (single/thread/process)
- `--workers`: 工作进程/线程数
- `--full`: 执行完整更新（包括周线）

### run_weekly_update.py
```bash
python run_weekly_update.py --mode single --workers 1 --test --debug
```
- `--mode`: 并发模式 (single/thread/process)
- `--workers`: 工作进程/线程数
- `--test`: 测试模式，只处理少量股票
- `--debug`: 调试模式，显示详细检测信息

## 测试并发模式
```bash
# 测试所有模式
python test_concurrency_modes.py --mode all --workers 2

# 只测试单线程模式
python test_concurrency_modes.py --mode single

# 测试多线程模式，跳过可能触发限制的多进程模式
python test_concurrency_modes.py --mode all --skip-process
```

## 推荐配置

### 稳定优先配置
```bash
# 避免所有并发问题
python daily_update.py --mode single --workers 1
```

### 平衡配置
```bash
# 在稳定性和速度之间取得平衡
python daily_update.py --mode thread --workers 3
```

### 性能优先配置
```bash
# 追求最快速度，可能触发限制
python daily_update.py --mode process --workers 6
```

## 故障排除

### 1. 遇到baostock访问限制
```bash
# 切换到单线程模式
python bao_data_downloader.py --mode single --workers 1

# 或使用多线程模式
python bao_data_downloader.py --mode thread --workers 2
```

### 2. 下载速度过慢
```bash
# 增加工作线程数（多线程模式）
python bao_data_downloader.py --mode thread --workers 4

# 如果网络环境好，尝试多进程模式
python bao_data_downloader.py --mode process --workers 4
```

### 3. 测试模式
```bash
# 只处理少量股票进行测试
python run_weekly_update.py --mode single --workers 1 --test --debug
```

## 注意事项
1. **单线程模式**最稳定，但速度最慢
2. **多线程模式**在避免baostock限制的同时提供一定并发性
3. **多进程模式**速度最快，但可能触发baostock限制
4. 建议先使用测试模式验证当前网络环境下的最佳配置
5. 如果遇到频繁失败，建议降低工作进程/线程数