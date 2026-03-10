#!/usr/bin/env python3
"""
配置文件
"""

# 数据库配置
DB_CONFIG = {
    'host': '100.87.204.122',
    'port': 5432,
    'database': 'quant_db',
    'user': 'quant',
    'password': 'Quant@2025!Secure'
}

# 股票池筛选参数
POOL_CONFIG = {
    'min_market_cap': 500000,  # 最小市值（万元）：50亿
    'min_avg_amount': 50000,   # 最小日均成交额（千元）：5000万
    'min_list_days': 365,      # 最小上市天数：1年
    'target_size': (80, 120),  # 目标股票池大小
    'industries': [
        '半导体', '集成电路', '光学光电子', '通信设备',
        '计算机设备', '自动化设备', '机器人', '算力', 'AI'
    ]
}

# 股票过滤参数（v3.1 - 移除政策和北向资金）
FILTER_CONFIG = {
    'sma200_ratio': 0.9,       # 价格/SMA200最小比例
    'min_volume': 0,           # 最小成交量（非停牌）
    'target_size': (20, 40)    # 目标过滤后大小
}

# 策略参数（v3.1+ - 加权评分系统）
STRATEGY_PARAMS = {
    'theta_buy': 6.0,          # 买入乖离率阈值（%）- 用于评分计算
    'theta_sell': 15.0,        # 卖出乖离率阈值（%）
    'alpha_vol': 0.65,         # 缩量系数 - 限制在0.5~0.8
    'rsi_thresh': 35,          # RSI阈值 - 用于评分计算
    'score_threshold': 0.60,   # 信号评分阈值（0-1）- 降低以捕获更多信号
    'risk_per_trade': 0.02,    # 单笔风险（%）
    'max_position': 0.8,       # 最大仓位（%）
    'initial_cash': 1000000    # 初始资金
}

# 参数优化空间（v3.1+ - 加权评分系统）
PARAM_SPACE = {
    'theta_buy': (4.0, 10.0),   # BIAS评分参考值
    'theta_sell': (10.0, 20.0),
    'alpha_vol': (0.5, 0.8),    # 严格限制在0.5~0.8
    'rsi_thresh': (30, 40)      # RSI评分参考值
}

# 遗传算法参数
GA_CONFIG = {
    'population_size': 50,
    'generations': 50,
    'crossover_prob': 0.5,
    'mutation_prob': 0.2,
    'tournament_size': 3
}

# 回测参数
BACKTEST_CONFIG = {
    'initial_cash': 1000000,   # 初始资金
    'commission': 0.00025,     # 佣金
    'stamp_tax': 0.001,        # 印花税（卖出）
    'slippage': 0.002          # 滑点
}

# 数据集划分（v3.1 - 使用实际可用数据周期）
DATASET_CONFIG = {
    'train': {
        'start_date': '20230101',
        'end_date': '20241231'
    },
    'val': {
        'start_date': '20250101',
        'end_date': '20250630'
    },
    'test': {
        'start_date': '20250101',
        'end_date': '20260310'
    }
}

# 报告配置（v3.1）
REPORT_CONFIG = {
    'output_dir': './result_v3.1',
    'figure_dpi': 300,
    'figure_size': (12, 6)
}
