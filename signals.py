"""
信号生成模块：买入、卖出、止损信号
"""

import pandas as pd
import numpy as np


def generate_buy_signal(df, theta_buy=8.0, alpha_vol=0.6):
    """
    生成买入信号

    条件：
    1. Beta护航：SMA_60 > SMA_60_5d_ago
    2. 负乖离：BIAS_20 < -theta_buy
    3. 缩量：volume < alpha_vol * Vol_SMA_10
    4. 右侧确认：close > prev_close (收阳)

    Returns:
    --------
    pd.Series (bool)
    """
    buy_signal = (
        (df['SMA_60'] > df['SMA_60_5d_ago']) &           # Beta护航
        (df['BIAS_20'] < -theta_buy) &                    # 负乖离
        (df['volume'] < alpha_vol * df['Vol_SMA_10']) &   # 缩量
        (df['close'] > df['prev_close'])                  # 右侧确认
    )

    return buy_signal


def generate_sell_signal(df, theta_sell=15.0):
    """
    生成卖出信号

    条件（满足其一）：
    1. 正乖离：BIAS_20 > theta_sell
    2. 量价背离：volume > 2.0 * Vol_SMA_10 且 Upper_Shadow_Ratio > 0.6
    3. 破位止损：close < SMA_60 * 0.95

    Returns:
    --------
    pd.Series (bool)
    """
    sell_signal = (
        (df['BIAS_20'] > theta_sell) |                                          # 正乖离
        ((df['volume'] > 2.0 * df['Vol_SMA_10']) &
         (df['Upper_Shadow_Ratio'] > 0.6)) |                                    # 量价背离
        (df['close'] < df['SMA_60'] * 0.95)                                     # 破位止损
    )

    return sell_signal


def generate_signals(df, theta_buy=8.0, theta_sell=15.0, alpha_vol=0.6):
    """
    生成所有交易信号

    Returns:
    --------
    pd.DataFrame
        添加了 'buy_signal' 和 'sell_signal' 列
    """
    df = df.copy()

    df['buy_signal'] = generate_buy_signal(df, theta_buy, alpha_vol)
    df['sell_signal'] = generate_sell_signal(df, theta_sell)

    return df
