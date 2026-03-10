# 量化策略系统 v3.0

基于PostgreSQL数据库的政策驱动科技股量化策略系统。

## 项目概述

本项目实现了一个完整的量化交易策略系统，包括：

- 股票池筛选（80-120只科技股）
- 动态股票过滤（每日20-40只）
- 量化信号生成（BIAS + RSI + MACD + 缩量）
- 参数优化（遗传算法）
- 回测引擎（Backtrader）
- 报告生成

## 技术栈

- **数据库**: PostgreSQL 17.7
- **技术指标**: TA-Lib
- **回测引擎**: Backtrader
- **参数优化**: DEAP (遗传算法)
- **数据处理**: Pandas, NumPy
- **可视化**: Matplotlib

## 项目结构

```
quantv3/
├── config.py                    # 配置文件
├── data_loader.py               # 数据加载模块
├── stock_pool.py                # 股票池筛选
├── signal_generator.py          # 信号生成
├── main.py                      # 主程序
├── requirements.txt             # Python依赖
└── README.md                    # 本文件
```

## 安装依赖

```bash
# 安装 TA-Lib（需要系统级安装）
sudo apt-get install -y ta-lib

# 安装 Python 依赖
pip3 install -r requirements.txt
```

## 数据库配置

确保PostgreSQL数据库已配置并包含以下表：

- `kline_daily`: 日K线数据
- `technical_indicators`: 技术指标（已预计算）
- `stock_basic`: 股票基本信息
- `fina_indicator`: 财务指标
- `daily_basic`: 市值/换手率
- `moneyflow_hsgt`: 北向资金

## 使用方法

### 1. 基础测试

```bash
python3 main.py
```

### 2. 构建股票池

```bash
python3 stock_pool.py
```

### 3. 测试信号生成

```bash
python3 signal_generator.py
```

## 策略说明

### 买入信号

1. SMA60向上（趋势过滤）
2. BIAS20 < -6%（负乖离率，超跌）
3. Vol < 0.6 × Vol_SMA10（缩量）
4. RSI14 < 30（超卖）
5. MACD HIST转正（动能转强）
6. 阳线（Close > Open）

### 卖出信号

1. BIAS20 > 12%（正乖离率过大）
2. Close < SMA60 × 0.95（跌破均线5%）
3. 上影线过长（获利回吐）

## 预期指标

- 年化收益率: > 20%
- 最大回撤: < 15%
- 夏普比率: > 1.5
- 换手率: < 15%/月
- 胜率: > 60%

## 开发状态

### 已完成

- ✅ 配置模块
- ✅ 数据加载模块
- ✅ 股票池筛选
- ✅ 信号生成模块
- ✅ 主程序框架

### 待开发

- ⏳ 股票过滤模块 (stock_filter.py)
- ⏳ 参数优化模块 (optimizer.py)
- ⏳ 回测引擎 (backtest_engine.py)
- ⏳ 报告生成 (report_generator.py)

## 注意事项

1. 确保数据库连接正常
2. 技术指标表需要预先计算（使用 calculate_technical_indicators.py）
3. 首次运行建议使用小样本测试
4. 参数优化需要较长时间，建议后台运行

## 版本历史

- v3.0 (2026-03-10): 初始版本，基础功能实现

## 作者

Coder Agent (OpenClaw)

## 许可

MIT License
