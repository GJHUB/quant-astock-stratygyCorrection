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
    生成买卖信号（v3.1+ - 加权评分系统，修复买点稀疏问题）

    买入逻辑：加权评分（0-1）+ 阈值触发
    - 趋势权重: 0.25 (SMA60向上)
    - BIAS权重: 0.25 (负乖离率超跌)
    - 缩量权重: 0.15 (成交量萎缩)
    - RSI权重: 0.15 (超卖)
    - MACD权重: 0.10 (HIST转正)
    - 阳线权重: 0.10 (收盘>开盘)
    - 触发阈值: score > 0.70 (可配置)

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

    # 加权评分系统（0-1范围）- 调整权重分配以增加信号
    score = pd.Series(0.0, index=df.index)

    # 1. 趋势权重 0.20（降低）
    trend_up = (df['sma60'] > df['sma60'].shift(1)).astype(float)
    score += 0.20 * trend_up

    # 2. BIAS权重 0.30（提高，核心指标）- 负乖离率越大，分数越高
    # 调整计算方式：当BIAS < -theta_buy时给满分，否则线性衰减
    bias_score = np.clip((params['theta_buy'] - df['bias20']) / 15.0, 0, 1)
    score += 0.30 * bias_score

    # 3. 缩量权重 0.15
    vol_shrink = (df['vol'] < params['alpha_vol'] * df['vol_sma10']).astype(float)
    score += 0.15 * vol_shrink

    # 4. RSI权重 0.20（提高）- RSI越低，分数越高
    rsi_score = np.clip((params['rsi_thresh'] - df['rsi14']) / 30.0, 0, 1)
    score += 0.20 * rsi_score

    # 5. MACD权重 0.10
    macd_turn = (df['macd_hist'] > 0).astype(float)
    score += 0.10 * macd_turn

    # 6. 阳线权重 0.05（降低）
    is_yang = (df['close'] > df['open']).astype(float)
    score += 0.05 * is_yang

    # 流动性过滤（非停牌）
    liquidity_ok = (df['vol'] > 0)

    # 买入信号：score > 阈值 & 流动性OK
    score_threshold = params.get('score_threshold', 0.70)
    buy_cond = (score > score_threshold) & liquidity_ok

    # 卖出条件（保持不变）
    sell_cond = (
        (df['bias20'] > params['theta_sell']) |  # 正乖离率过大（15%）
        (df['close'] < df['sma60'] * 0.92) |  # 跌破均线8%
        (df['rsi14'] > 70)  # RSI超买
    )

    # 生成信号
    df['signal'] = 0
    df['signal_score'] = score  # 保存评分用于调试
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
