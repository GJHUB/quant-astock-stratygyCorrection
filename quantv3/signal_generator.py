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
    生成买卖信号
    
    买入条件：
    1. SMA60向上
    2. BIAS20 < -θ（负乖离率）
    3. Vol < α × Vol_SMA10（缩量）
    4. RSI14 < 30（超卖）
    5. MACD HIST转正
    6. 阳线（Close > Open）
    
    卖出条件：
    1. BIAS20 > 12%（正乖离率过大）
    2. Close < SMA60 * 0.95（跌破均线5%）
    3. 上影线过长
    
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
    
    # 买入条件
    buy_cond = (
        (df['sma60'] > df['sma60'].shift(5)) &  # SMA60向上
        (df['bias20'] < -params['theta_buy']) &  # 负乖离率
        (df['vol'] < params['alpha_vol'] * df['vol_sma10']) &  # 缩量
        (df['rsi14'] < params['rsi_thresh']) &  # RSI超卖
        (df['macd_hist'] > df['macd_hist'].shift(1)) &  # MACD HIST转正
        (df['close'] > df['open'])  # 阳线
    )
    
    # 卖出条件
    sell_cond = (
        (df['bias20'] > params['theta_sell']) |  # 正乖离率过大
        (df['close'] < df['sma60'] * 0.95) |  # 跌破均线5%
        ((df['high'] - df['close']) > 0.05 * (df['high'] - df['low']))  # 上影线过长
    )
    
    # 生成信号（T+1）
    df['signal'] = 0
    df.loc[buy_cond, 'signal'] = 1
    df.loc[sell_cond, 'signal'] = -1
    
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
