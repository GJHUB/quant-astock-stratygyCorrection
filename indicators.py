"""
技术指标计算模块：SMA, BIAS, ATR
"""

import pandas as pd
import numpy as np


def calculate_sma(series, window):
    """计算简单移动平均线"""
    return series.rolling(window=window).mean()


def calculate_bias(close, sma_window=20):
    """
    计算乖离率 BIAS
    BIAS = (Close - SMA) / SMA * 100
    """
    sma = calculate_sma(close, sma_window)
    bias = (close - sma) / sma * 100
    return bias


def calculate_atr(high, low, close, window=14):
    """
    计算平均真实波动幅度 ATR
    TR = max(H-L, |H-C_prev|, |L-C_prev|)
    ATR = SMA(TR, window)
    """
    prev_close = close.shift(1)

    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()

    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=window).mean()

    return atr


def calculate_all_indicators(df):
    """
    计算所有技术指标

    Parameters:
    -----------
    df : pd.DataFrame
        包含 open, high, low, close, volume

    Returns:
    --------
    pd.DataFrame
        添加了技术指标列的DataFrame
    """
    df = df.copy()

    # 均线
    df['SMA_20'] = calculate_sma(df['close'], 20)
    df['SMA_60'] = calculate_sma(df['close'], 60)
    df['SMA_60_5d_ago'] = df['SMA_60'].shift(5)

    # 乖离率
    df['BIAS_20'] = calculate_bias(df['close'], 20)

    # 成交量均线
    df['Vol_SMA_10'] = calculate_sma(df['volume'], 10)

    # ATR
    df['ATR_14'] = calculate_atr(df['high'], df['low'], df['close'], 14)

    # 上影线比例
    upper_shadow = df['high'] - df[['close', 'open']].max(axis=1)
    body_total = df['high'] - df['low'] + 1e-8  # 避免除零
    df['Upper_Shadow_Ratio'] = upper_shadow / body_total

    # 前一日收盘价（用于右侧确认）
    df['prev_close'] = df['close'].shift(1)

    return df
