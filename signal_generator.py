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


def get_policy_score(dates: pd.Series) -> pd.Series:
    """
    获取政策评分（预留接口，v3.2）

    未来可接入BERT NLP分析政策文本，当前返回默认值
    支持安全降级：无数据时返回0

    Parameters:
    -----------
    dates : pd.Series
        日期序列

    Returns:
    --------
    pd.Series
        政策评分（0-1范围）
    """
    # 当前实现：返回0（无政策加成）
    # 未来扩展：接入政策NLP分析、北向资金等
    return pd.Series(0.0, index=dates.index if hasattr(dates, 'index') else range(len(dates)))


def generate_signals(df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
    """
    生成买卖信号（v3.2 - 加权评分系统，提升交易次数）

    买入逻辑：加权评分（0-1）+ 阈值触发（v3.2公式）
    - 趋势权重: 0.25 (SMA60向上)
    - BIAS权重: 0.25 (负乖离率超跌，分母放宽至8)
    - 缩量权重: 0.15 (成交量萎缩)
    - RSI权重: 0.15 (超卖，分母放宽至15)
    - 政策权重: 0.20 (预留接口，当前降级为0)
    - 触发阈值: score > 0.65 (可配置0.60-0.70)

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

    # 加权评分系统（0-1范围）- v3.2权重分配
    score = pd.Series(0.0, index=df.index)

    # 1. 趋势权重 0.25
    trend_up = (df['sma60'] > df['sma60'].shift(1)).astype(float)
    score += 0.25 * trend_up

    # 2. BIAS权重 0.25 - 负乖离率越大，分数越高（分母放宽至8）
    # theta_buy为负值（如-6），当BIAS < theta_buy时给高分
    bias_score = np.clip((params['theta_buy'] - df['bias20']) / 8.0, 0, 1)
    score += 0.25 * bias_score

    # 3. 缩量权重 0.15
    vol_shrink = (df['vol'] < params['alpha_vol'] * df['vol_sma10']).astype(float)
    score += 0.15 * vol_shrink

    # 4. RSI权重 0.15 - RSI越低，分数越高（分母放宽至15）
    rsi_score = np.clip((params['rsi_thresh'] - df['rsi14']) / 15.0, 0, 1)
    score += 0.15 * rsi_score

    # 5. 政策权重 0.20（预留接口，支持安全降级）
    try:
        policy_score = get_policy_score(df.index)
        score += 0.20 * np.clip(policy_score, 0, 1)
    except Exception as e:
        logger.warning(f"政策评分计算失败，降级为0: {e}")
        # 安全降级：无政策数据时不影响其他评分

    # 流动性过滤（v3.2放宽至3000万成交额）
    min_amount = params.get('min_amount', 30000000)
    if 'amount' in df.columns:
        liquidity_ok = (df['vol'] > 0) & (df['amount'] > min_amount)
    else:
        liquidity_ok = (df['vol'] > 0)

    # 买入信号：score > 阈值 & 流动性OK
    score_threshold = params.get('score_threshold', 0.65)
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
