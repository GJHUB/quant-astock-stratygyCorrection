#!/usr/bin/env python3
"""
测试信号生成 - 验证加权评分系统
"""

import sys
from data_loader import load_stock_data
from signal_generator import generate_signals

# 测试参数（符合优化方案）
test_params = {
    'theta_buy': 6.0,
    'theta_sell': 15.0,
    'alpha_vol': 0.65,  # 严格在0.5~0.8范围内
    'rsi_thresh': 35,
    'score_threshold': 0.60,
    'risk_per_trade': 0.02,
    'max_position': 0.8,
    'initial_cash': 1000000
}

# 测试单只股票
ts_code = '300394.SZ'
df = load_stock_data(ts_code, '20250101', '20260310')

if df is not None:
    df_signals = generate_signals(df, test_params)

    # 统计信号
    buy_signals = df_signals[df_signals['signal'] == 1]
    sell_signals = df_signals[df_signals['signal'] == -1]

    print(f"\n{'='*80}")
    print(f"股票: {ts_code}")
    print(f"数据周期: 20250101 - 20260310")
    print(f"{'='*80}")
    print(f"\n参数:")
    for k, v in test_params.items():
        print(f"  {k}: {v}")

    print(f"\n信号统计:")
    print(f"  买入信号: {len(buy_signals)}")
    print(f"  卖出信号: {len(sell_signals)}")

    if len(buy_signals) > 0:
        print(f"\n最近5个买入信号:")
        print(buy_signals[['close', 'signal_score', 'bias20', 'rsi14', 'vol', 'vol_sma10']].tail(5))

    # 显示评分分布
    print(f"\n评分统计:")
    print(f"  最高评分: {df_signals['signal_score'].max():.3f}")
    print(f"  平均评分: {df_signals['signal_score'].mean():.3f}")
    print(f"  评分>0.70的天数: {(df_signals['signal_score'] > 0.70).sum()}")
    print(f"  评分>0.60的天数: {(df_signals['signal_score'] > 0.60).sum()}")

    print(f"\n最高评分的5天:")
    top_scores = df_signals.nlargest(5, 'signal_score')[['close', 'signal_score', 'bias20', 'rsi14', 'macd_hist', 'vol', 'vol_sma10']]
    print(top_scores)

    print(f"\n{'='*80}")
else:
    print(f"无法加载股票数据: {ts_code}")
    sys.exit(1)
