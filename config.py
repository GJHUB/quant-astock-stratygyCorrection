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

# 策略参数（v3.3 - 4权重可调+归一化+A股微观结构修正）
STRATEGY_PARAMS = {
    # v3.3新增：4个可调权重（总和会自动归一化为1.0）
    'w_trend': 0.25,           # 趋势权重（长线Beta过滤）
    'w_bias': 0.30,            # BIAS权重（短线Alpha核心）
    'w_vol': 0.25,             # 缩量权重（A股特有筹码锁定）
    'w_rsi': 0.20,             # RSI权重（动量互补）

    # 原有参数
    'theta_buy': -7.0,         # 买入乖离率阈值（%）- v3.3调整为-7（负值表示超跌）
    'theta_sell': 12.0,        # 卖出乖离率阈值（%）- v3.3调整为12（对称卖出）
    'alpha_vol': 0.80,         # 缩量系数 - v3.3调整范围0.70~0.90
    'rsi_thresh': 30,          # RSI阈值 - 用于评分计算
    'score_threshold': 0.50,   # 信号评分阈值（0-1）- v3.3调整为0.50，可配置0.40-0.60
    'risk_per_trade': 0.02,    # 单笔风险（%）
    'max_position': 0.8,       # 最大仓位（%）
    'initial_cash': 1000000,   # 初始资金
    'min_amount': 30000000     # 最小成交额（元）
}

# 参数优化空间（v3.3 - 10维联合优化）
PARAM_SPACE = {
    # v3.3新增：4个权重参数（会自动归一化，这里定义搜索范围）
    'w_trend': (0.15, 0.35),    # 趋势权重搜索范围
    'w_bias': (0.20, 0.35),     # BIAS权重搜索范围
    'w_vol': (0.10, 0.20),      # 缩量权重搜索范围
    'w_rsi': (0.10, 0.20),      # RSI权重搜索范围

    # 原有参数（v3.3调整搜索范围）
    'theta_buy': (-10.0, -6.0),  # BIAS评分参考值（负值）- v3.3扩展范围
    'theta_sell': (8.0, 14.0),   # v3.3调整范围
    'alpha_vol': (0.70, 0.90),   # v3.3调整范围0.70~0.90
    'rsi_thresh': (25, 35),      # RSI评分参考值
    'score_threshold': (0.40, 0.60)  # v3.3调整范围0.40~0.60
}

# 遗传算法参数（v3.2 - 扩展搜索强度）
GA_CONFIG = {
    'population_size': 100,     # v3.2: 从50提升到100
    'generations': 100,         # v3.2: 从50提升到100
    'crossover_prob': 0.5,
    'mutation_prob': 0.2,
    'tournament_size': 3,
    'min_trades': 20            # v3.2.1: 最小交易次数目标（先降低做可行性验证）
}

# 回测参数（v3.3 - 真实交易成本）
BACKTEST_CONFIG = {
    'initial_cash': 1000000,   # 初始资金
    'commission': 0.00025,     # 佣金（万2.5）
    'stamp_tax': 0.001,        # 印花税（0.1%，仅卖出）
    'slippage': 0.0003         # 滑点（0.03%）- v3.3调整为更真实的滑点
}

# 数据集划分（v3.2 - 全样本周期 + WFO）
DATASET_CONFIG = {
    'full_period': {
        'start_date': '20180101',
        'end_date': '20260310'
    },
    'wfo': {
        'train_window_years': 3,      # 训练窗口：3年
        'val_window_months': 6,       # 验证窗口：6个月
        'step_months': 6              # 滚动步长：6个月
    },
    'oos_test': {
        'primary': {
            'start_date': '20250101',
            'end_date': '20260310',
            'description': '主要样本外测试集 (2025-2026)'
        },
        'stress_test': {
            'start_date': '20210101',
            'end_date': '20231231',
            'description': '压力测试集 (2021-2023)'
        }
    }
}

# 报告配置（v3.3）
REPORT_CONFIG = {
    'output_dir': './result_v3.3',
    'figure_dpi': 300,
    'figure_size': (12, 6)
}
