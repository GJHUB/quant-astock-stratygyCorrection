"""
配置文件：数据库连接、策略参数
"""

# 数据库配置
DB_CONFIG = {
    'host': '100.87.204.122',
    'port': 5432,
    'database': 'quant_db',
    'user': 'quant',
    'password': 'Quant@2025!Secure'
}

# 策略参数（默认值，WFO会优化这些参数）
STRATEGY_PARAMS = {
    'theta_buy': 8.0,      # 负乖离率阈值
    'theta_sell': 15.0,    # 正乖离率阈值
    'alpha_vol': 0.6,      # 缩量系数
    'R': 0.01,             # 单笔风险敞口比例（1%）
}

# WFO优化参数空间
WFO_PARAM_SPACE = {
    'theta_buy': (6.0, 12.0, 1.0),      # (最小值, 最大值, 步长)
    'theta_sell': (10.0, 20.0, 2.0),
    'alpha_vol': (0.4, 0.7, 0.1),
    'R': (0.005, 0.02, 0.005),
}

# WFO时间窗口配置
WFO_CONFIG = {
    'train_months': 12,    # 训练集12个月
    'test_months': 3,      # 测试集3个月
}

# 回测配置
BACKTEST_CONFIG = {
    'initial_capital': 1000000,     # 初始资金100万
    'commission_buy': 0.00025,      # 买入佣金0.025%
    'commission_sell': 0.00075,     # 卖出佣金0.075%
    'stamp_tax': 0.0005,            # 印花税0.05%
    'slippage': 0.002,              # 双边滑点0.2%
    'lot_size': 100,                # A股最小交易单位100股
}

# 股票池配置
STOCK_POOL_CONFIG = {
    'sector': '科技',               # 板块筛选
    'top_n': 120,                   # 选取前120只
    'volatility_window': 60,        # 波动率计算窗口
}

# 数据日期范围
DATA_CONFIG = {
    'start_date': '20230101',       # 数据起始日期
    'end_date': '20260309',         # 数据结束日期
}
