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


def get_policy_score(dates) -> pd.Series:
    """
    获取政策评分（预留接口，v3.2）

    未来可接入BERT NLP分析政策文本，当前返回默认值
    支持安全降级：无数据时返回0

    Parameters:
    -----------
    dates : pd.Series | pd.Index | list
        日期序列

    Returns:
    --------
    pd.Series
        政策评分（0-1范围）
    """
    # 关键修复：必须与行情df使用同一索引，避免Series对齐后整列变NaN
    if isinstance(dates, (pd.Series, pd.Index)):
        idx = dates
    else:
        idx = pd.Index(dates)
    return pd.Series(0.0, index=idx)


def generate_signals(df: pd.DataFrame, params: Dict = None) -> pd.DataFrame:
    """
    生成买卖信号（v3.3 - 4权重可调+归一化+A股微观结构修正）

    v3.3改进点：
    1. 权重可调：w_trend, w_bias, w_vol, w_rsi（总和强制归一化为1.0）
    2. A股微观结构修正：跌停过滤（-9.5%）、停牌处理（成交量=0）
    3. 真实交易成本：印花税0.1%、佣金万2.5、滑点0.03%
    4. 移除政策权重（v3.2的0.20权重分配到其他4个因子）

    买入逻辑：加权评分（0-1）+ 阈值触发
    - 趋势权重: w_trend (SMA60向上，长线Beta过滤)
    - BIAS权重: w_bias (负乖离率超跌，短线Alpha核心)
    - 缩量权重: w_vol (成交量萎缩，A股特有筹码锁定)
    - RSI权重: w_rsi (超卖，动量互补)
    - 触发阈值: score > score_threshold (可配置0.40-0.60)

    卖出条件：
    1. BIAS20 > theta_sell（正乖离率过大，对称卖出）
    2. score < score_threshold * 0.6（评分回落）

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

    # v3.3: 权重归一化（强制总和=1.0）
    w = {
        'trend': params.get('w_trend', 0.25),
        'bias':  params.get('w_bias',  0.30),
        'vol':   params.get('w_vol',   0.25),
        'rsi':   params.get('w_rsi',   0.20)
    }
    total_w = sum(w.values())
    if total_w > 0:
        w = {k: v / total_w for k, v in w.items()}  # 归一化
    else:
        # 防御性编程：如果权重全为0，使用默认均分
        w = {'trend': 0.25, 'bias': 0.25, 'vol': 0.25, 'rsi': 0.25}

    # 加权评分系统（0-1范围）- v3.3可调权重
    score = pd.Series(0.0, index=df.index)

    # 1. 趋势权重（长线Beta过滤）
    trend_up = (df['sma60'] > df['sma60'].shift(1)).astype(float)
    if trend_up.isna().any():
        nan_count = trend_up.isna().sum()
        logger.error(f"trend_up 包含 {nan_count} 个 NaN 值，请检查 sma60 数据")
        raise ValueError(f"trend_up contains {nan_count} NaN values")
    score += w['trend'] * trend_up

    # 2. BIAS权重（短线Alpha核心）- 负乖离率越大，分数越高
    # theta_buy为负值（如-6），当BIAS < theta_buy时给高分
    bias_score = ((params['theta_buy'] - df['bias20']) / 8.0).clip(0, 1)
    if bias_score.isna().any():
        nan_count = bias_score.isna().sum()
        logger.error(f"bias_score 包含 {nan_count} 个 NaN 值，请检查 bias20 数据")
        raise ValueError(f"bias_score contains {nan_count} NaN values")
    score += w['bias'] * bias_score

    # 3. 缩量权重（A股特有筹码锁定）
    vol_shrink = (df['vol'] < params['alpha_vol'] * df['vol_sma10']).astype(float)
    if vol_shrink.isna().any():
        nan_count = vol_shrink.isna().sum()
        logger.error(f"vol_shrink 包含 {nan_count} 个 NaN 值，请检查 vol_sma10 数据")
        raise ValueError(f"vol_shrink contains {nan_count} NaN values")
    score += w['vol'] * vol_shrink

    # 4. RSI权重（动量互补）- RSI越低，分数越高
    rsi_score = ((params['rsi_thresh'] - df['rsi14']) / 15.0).clip(0, 1)
    if rsi_score.isna().any():
        nan_count = rsi_score.isna().sum()
        logger.error(f"rsi_score 包含 {nan_count} 个 NaN 值，请检查 rsi14 数据")
        raise ValueError(f"rsi_score contains {nan_count} NaN values")
    score += w['rsi'] * rsi_score
    
    # 最终检查：确保 score 没有 NaN
    if score.isna().any():
        nan_count = score.isna().sum()
        logger.error(f"最终 score 包含 {nan_count} 个 NaN 值")
        raise ValueError(f"Final score contains {nan_count} NaN values")

    # v3.3: A股微观结构修正
    # 1. 跌停过滤（日内跌幅 > -9.5%，避免跌停板无法买入）
    pct_change = df['close'].pct_change()
    not_limit_down = pct_change > -0.095

    # 2. 停牌处理（成交量 > 0，避免停牌期间误触发）
    not_suspended = df['vol'] > 0

    # 流动性过滤（v3.2放宽至3000万成交额）
    min_amount = params.get('min_amount', 30000000)
    if 'amount' in df.columns:
        liquidity_ok = (df['amount'] > min_amount)
    else:
        liquidity_ok = pd.Series(True, index=df.index)

    # 买入信号：score > 阈值 & 流动性OK & 非跌停 & 非停牌
    score_threshold = params.get('score_threshold', 0.50)
    buy_cond = (score > score_threshold) & liquidity_ok & not_limit_down & not_suspended

    # v3.3: 卖出条件（简化为对称BIAS + score回落）
    sell_cond = (
        (df['bias20'] > params['theta_sell']) |  # 正乖离率过大（对称卖出）
        (score < score_threshold * 0.6)  # 评分回落35%
    )

    # 生成信号
    df['signal'] = 0
    df['signal_score'] = score  # 保存评分用于调试
    df.loc[buy_cond, 'signal'] = 1
    df.loc[sell_cond, 'signal'] = -1

    # T+1 shift（信号延迟1天执行）
    df['signal'] = df['signal'].shift(1).fillna(0)

    # v3.3: 真实交易成本计算（印花税0.1% + 佣金万2.5 + 滑点0.03%）
    df['transaction_cost'] = 0.0
    df.loc[df['signal'] == 1, 'transaction_cost'] = 0.00025 + 0.0003  # 买入：佣金+滑点
    df.loc[df['signal'] == -1, 'transaction_cost'] = 0.001 + 0.00025 + 0.0003  # 卖出：印花税+佣金+滑点

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
