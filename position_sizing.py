"""
仓位管理模块：ATR动态仓位计算
"""

import numpy as np
from config import BACKTEST_CONFIG


def calculate_position_size(atr, total_capital, risk_per_trade=0.01, price=None):
    """
    计算ATR动态仓位

    公式：Shares = (TotalCapital * R) / ATR
    A股约束：向下取整到100股

    Parameters:
    -----------
    atr : float
        14日ATR值
    total_capital : float
        账户总资金
    risk_per_trade : float
        单笔风险敞口比例
    price : float, optional
        当前价格（用于检查是否超过总资金）

    Returns:
    --------
    int
        应买入的股数（100的整数倍）
    """
    if np.isnan(atr) or atr <= 0:
        return 0

    # 计算理论股数
    risk_amount = total_capital * risk_per_trade
    shares = risk_amount / atr

    # 向下取整到100股
    shares = int(shares // BACKTEST_CONFIG['lot_size']) * BACKTEST_CONFIG['lot_size']

    # 检查是否超过总资金（如果提供了价格）
    if price is not None and shares > 0:
        required_capital = shares * price
        if required_capital > total_capital:
            # 按总资金重新计算
            shares = int((total_capital / price) // BACKTEST_CONFIG['lot_size']) * BACKTEST_CONFIG['lot_size']

    return max(0, shares)


def add_position_sizing(df, total_capital, risk_per_trade=0.01):
    """
    为DataFrame添加仓位计算列

    Parameters:
    -----------
    df : pd.DataFrame
        包含 'ATR_14', 'buy_signal', 'close' 列
    total_capital : float
        账户总资金
    risk_per_trade : float
        单笔风险敞口比例

    Returns:
    --------
    pd.DataFrame
        添加了 'target_shares' 列
    """
    df = df.copy()

    df['target_shares'] = 0

    # 只在买入信号时计算仓位
    buy_mask = df['buy_signal'] == True

    for idx in df[buy_mask].index:
        atr = df.loc[idx, 'ATR_14']
        price = df.loc[idx, 'close']
        shares = calculate_position_size(atr, total_capital, risk_per_trade, price)
        df.loc[idx, 'target_shares'] = shares

    return df
