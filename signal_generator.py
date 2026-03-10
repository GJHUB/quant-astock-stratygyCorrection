#!/usr/bin/env python3
"""
信号生成模块
生成买卖信号
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict

from config import STRATEGY_PARAMS

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_signals(df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
    """
    生成买卖信号（v3.1 - 大幅放宽阈值，保留T+1 shift）

    买入条件（v3.1大幅放宽）：
    1. SMA60向上 OR Close > SMA60（趋势向上或在均线上方）
    2. BIAS20 < -θ（负乖离率，阈值放宽至3%）
    3. Vol < α × Vol_SMA10（缩量，阈值放宽至1.2倍）
    4. RSI14 < thresh（超卖，阈值放宽至45）
    5. MACD HIST > 0 OR HIST转正（放宽MACD条件）

    卖出条件：
    1. BIAS20 > 15%（正乖离率过大）
    2. Close < SMA60 * 0.92（跌破均线8%）
    3. RSI14 > 70（超买）

    Parameters:
    -----------
    df : pd.DataFrame
        包含K线数据和技术指标
    params : Dict
        策略参数

    Returns:
    --------
    pd.DataFrame
        添加 'signal' 列（1=买入, -1=卖出, 0=持有）
    """
    if params is None:
        params = STRATEGY_PARAMS

    df = df.copy()

    # 买入条件（v3.1 - 大幅放宽阈值）
    buy_cond = (
        ((df['sma60'] > df['sma60'].shift(5)) | (df['close'] > df['sma60'])) &  # 趋势向上或在均线上方
        (df['bias20'] < -params['theta_buy']) &  # 负乖离率（放宽至3%）
        (df['vol'] < params['alpha_vol'] * df['vol_sma10']) &  # 缩量（放宽至1.2倍）
        (df['vol'] > 0) &  # 非停牌
        (df['rsi14'] < params['rsi_thresh']) &  # RSI超卖（放宽至45）
        ((df['macd_hist'] > 0) | (df['macd_hist'] > df['macd_hist'].shift(1)))  # MACD为正或转正
    )

    # 卖出条件（放宽）
    sell_cond = (
        (df['bias20'] > params['theta_sell']) |  # 正乖离率过大（15%）
        (df['close'] < df['sma60'] * 0.92) |  # 跌破均线8%
        (df['rsi14'] > 70)  # RSI超买
    )

    # 生成信号
    df['signal'] = 0
    df.loc[buy_cond, 'signal'] = 1
    df.loc[sell_cond, 'signal'] = -1

    # T+1 shift（信号延迟1天执行）
    df['signal'] = df['signal'].shift(1).fillna(0)

    # 计算目标仓位（基于ATR）
    df['target_shares'] = 0
    risk_capital = params.get('initial_cash', 1000000) * params['risk_per_trade']
    df.loc[df['signal'] == 1, 'target_shares'] = (
        (risk_capital / df['atr14'] / 100).fillna(0).astype(int) * 100
    )

    return df


def calculate_position_size(capital: float, atr: float, risk_per_trade: float = 0.02) -> int:
    """
    计算仓位大小（基于ATR）
    
    Parameters:
    -----------
    capital : float
        可用资金
    atr : float
        ATR值
    risk_per_trade : float
        单笔风险比例
    
    Returns:
    --------
    int
        股数（整百股）
    """
    if atr <= 0 or pd.isna(atr):
        return 0
    
    risk_capital = capital * risk_per_trade
    shares = int(risk_capital / atr / 100) * 100
    
    return shares


if __name__ == '__main__':
    # 测试
    from data_loader import load_stock_data
    
    df = load_stock_data('300394.SZ', '20250101', '20260309')
    if df is not None:
        df_with_signals = generate_signals(df)
        print(f"\n信号统计:")
        print(f"买入信号: {(df_with_signals['signal'] == 1).sum()}")
        print(f"卖出信号: {(df_with_signals['signal'] == -1).sum()}")
        print(f"\n最近10个信号:")
        print(df_with_signals[df_with_signals['signal'] != 0][['close', 'signal', 'bias20', 'rsi14']].tail(10))
