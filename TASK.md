# 量化策略系统 v3.0 开发任务

## 项目概述
基于PostgreSQL数据库的政策驱动科技股量化策略系统。

## 数据库配置
- 主机：100.87.204.122
- 数据库：quant_db
- 用户：quant
- 密码：Quant@2025!Secure

## 核心模块

### 1. config.py - 配置文件
- 数据库连接配置
- 股票池筛选参数
- 策略参数（theta_buy, theta_sell, alpha_vol, rsi_thresh）
- 回测参数（初始资金、佣金、印花税）
- 数据集划分（训练集2024-2025，测试集2026）

### 2. data_loader.py - 数据加载模块
- get_db_connection(): 获取数据库连接
- load_stock_data(ts_code, start_date, end_date): 加载单只股票K线+技术指标
- load_multiple_stocks(stock_pool, start_date, end_date): 批量加载
- load_financial_data(ts_code, end_date): 加载财务数据
- load_north_flow(trade_date): 加载北向资金

### 3. stock_pool.py - 股票池筛选
从已有技术指标的82只股票中筛选：
- 按成交额排序
- 至少30个交易日数据
- 日均成交额 > 1000万（降低门槛）
- 返回股票代码列表

### 4. stock_filter.py - 股票过滤
每日筛选20-40只高质量股票：
- ROE > 15%
- EPS增长 > 20% YoY
- SMA60向上
- Close > SMA200 * 0.9
- 北向资金净流入 > 0

### 5. signal_generator.py - 信号生成
买入信号（6个条件同时满足）：
1. SMA60向上（趋势过滤）
2. BIAS20 < -θ（默认-6%，负乖离率）
3. Vol < α × Vol_SMA10（默认0.6倍，缩量）
4. RSI14 < 30（超卖）
5. MACD HIST转正（HIST > HIST_prev）
6. 阳线（Close > Open）

卖出信号（满足任一条件）：
1. BIAS20 > 12%（正乖离率过大）
2. Close < SMA60 * 0.95（跌破均线5%）
3. 上影线过长（(High-Close) > 0.05*(High-Low)）

仓位计算：
- 基于ATR的风险控制
- 单笔风险2%
- Shares = (Capital * Risk) / ATR / 100 * 100（整百股）

### 6. optimizer.py - 参数优化
使用DEAP遗传算法：
- 参数空间：
  - theta_buy: 4.0-10.0
  - theta_sell: 10.0-20.0
  - alpha_vol: 0.4-0.7
  - rsi_thresh: 20-40
- 种群大小：50
- 进化代数：50
- 交叉概率：0.5
- 变异概率：0.2
- 目标函数：Calmar Ratio - 换手惩罚
  - Calmar = Annual Return / Max Drawdown
  - Penalty = max(0, turnover - 0.15) * 10

### 7. backtest_engine.py - 回测引擎
使用Backtrader框架：
- T+1交易
- 佣金：0.00025
- 印花税：0.001（卖出）
- 滑点：0.002
- 初始资金：100万
- 计算指标：
  - 年化收益率
  - 最大回撤
  - 夏普比率
  - 换手率
  - 胜率
- 生成净值曲线图

### 8. report_generator.py - 报告生成
生成Markdown报告：
- 回测指标汇总表
- 净值曲线图（PNG）
- 买点标注图
- 参数配置
- 风险分析
- 归因分析（Beta/Alpha）

### 9. main.py - 主程序
完整执行流程：
1. 构建股票池
2. 划分数据集
3. 加载训练集数据
4. 参数优化（遗传算法）
5. 测试集回测
6. 生成报告

## 数据表结构
- kline_daily: 日K线（ts_code, trade_date, open, high, low, close, vol, amount）
- technical_indicators: 技术指标（sma5/10/20/60/200, bias20, rsi14, macd_hist, atr14, boll_upper/lower, kdj_k/d/j, vol_sma10）
- stock_basic: 股票基本信息（可能为空）
- fina_indicator: 财务指标（roe, eps, netprofit_yoy）
- daily_basic: 市值/换手率（total_mv, turnover_rate）
- moneyflow_hsgt: 北向资金（trade_date, north_money）

## 技术要求
1. 使用psycopg2连接PostgreSQL
2. 技术指标从technical_indicators表读取（已预计算）
3. 使用pandas处理数据
4. 使用backtrader进行回测
5. 使用deap进行遗传算法优化
6. 使用matplotlib生成图表
7. 完整的错误处理和日志记录
8. 代码注释清晰，符合PEP8规范

## 预期指标
- 年化收益率 > 20%
- 最大回撤 < 15%
- 夏普比率 > 1.5
- 换手率 < 15%/月
- 胜率 > 60%

## 注意事项
1. stock_basic表可能为空，直接使用有技术指标的股票
2. 买入信号可能为0，需要参数优化
3. 测试集数据较少（2026年仅2个月）
4. 建议先用小样本测试，再全量运行
5. 参数优化需要较长时间

## 输出文件
- requirements.txt: Python依赖
- README.md: 项目说明文档
- 所有Python模块文件
- 测试脚本

请开发完整的、可运行的代码，包括所有模块和主程序。
