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

    # 账户状态管理
    initial_cash = params.get('initial_cash', 1000000)
    cash = initial_cash
    shares = 0

    # 持仓状态管理：添加 position 列（0=空仓，1=持仓）
    df['position'] = 0
    df['signal'] = 0
    df['signal_score'] = score  # 保存评分用于调试

    # 添加新列记录账户状态
    df['cash'] = 0.0
    df['shares'] = 0
    df['position_value'] = 0.0
    df['buy_price'] = 0.0
    df['sell_price'] = 0.0

    score_threshold = params.get('score_threshold', 0.50)

    # 计算目标仓位（基于ATR）
    df['target_shares'] = 0
    risk_capital = params.get('initial_cash', 1000000) * params['risk_per_trade']
    # 处理 atr14 为 0 或 NaN 的情况，避免除零和 inf
    atr_safe = df['atr14'].replace(0, np.nan).fillna(1.0)  # 0 替换为 NaN，然后填充为 1.0
    target_shares_calc = (risk_capital / atr_safe / 100).clip(0, 1e6).fillna(0).astype(int) * 100
    df['target_shares'] = target_shares_calc

    # 逐行处理买入卖出逻辑，避免同时满足条件时的冲突
    for i in range(1, len(df)):
        prev_position = df.iloc[i-1]['position']
        close_price = df['close'].iloc[i]

        # 更新当前持仓市值
        position_value = shares * close_price
        df.iloc[i, df.columns.get_loc('position_value')] = position_value
        df.iloc[i, df.columns.get_loc('cash')] = cash
        df.iloc[i, df.columns.get_loc('shares')] = shares

        # 买入条件：前一天空仓 且 score > threshold 且流动性OK且非跌停且非停牌
        buy_cond = (
            prev_position == 0 and
            score.iloc[i] > score_threshold and
            liquidity_ok.iloc[i] and
            not_limit_down.iloc[i] and
            not_suspended.iloc[i] and
            cash > 0
        )

        # 卖出条件：前一天持仓 且 (bias20 > theta_sell 或 score < threshold*0.6)
        sell_cond = (
            prev_position == 1 and
            shares > 0 and
            (df['bias20'].iloc[i] > params['theta_sell'] or
             score.iloc[i] < score_threshold * 0.6)
        )

        # 更新信号和持仓状态
        if buy_cond:
            # 计算目标买入股数（基于ATR风险控制）
            target_shares = df['target_shares'].iloc[i] if df['target_shares'].iloc[i] > 0 else 0

            # 按照当天收盘价计算可买入股数（整百股）
            max_affordable_shares = (cash // close_price // 100) * 100
            buy_shares = min(target_shares, max_affordable_shares) if target_shares > 0 else max_affordable_shares

            if buy_shares > 0:
                # 执行买入
                buy_amount = buy_shares * close_price
                cash -= buy_amount
                shares += buy_shares

                # 记录买入信号和价格
                df.iloc[i, df.columns.get_loc('signal')] = 1
                df.iloc[i, df.columns.get_loc('position')] = 1
                df.iloc[i, df.columns.get_loc('buy_price')] = close_price
            else:
                # 资金不足，继承前一天状态
                df.iloc[i, df.columns.get_loc('position')] = prev_position

        elif sell_cond:
            # 按照当天收盘价卖出全部持仓
            if shares > 0:
                sell_amount = shares * close_price
                cash += sell_amount
                shares = 0

                # 记录卖出信号和价格
                df.iloc[i, df.columns.get_loc('signal')] = -1
                df.iloc[i, df.columns.get_loc('position')] = 0
                df.iloc[i, df.columns.get_loc('sell_price')] = close_price
            else:
                # 没有持仓，继承前一天状态
                df.iloc[i, df.columns.get_loc('position')] = prev_position
        else:
            # 继承前一天的持仓状态
            df.iloc[i, df.columns.get_loc('position')] = prev_position

        # 更新最终的账户状态
        df.iloc[i, df.columns.get_loc('cash')] = cash
        df.iloc[i, df.columns.get_loc('shares')] = shares
        df.iloc[i, df.columns.get_loc('position_value')] = shares * close_price

    # T+1 shift（信号延迟1天执行）
    df['signal'] = df['signal'].shift(1).fillna(0)

    # v3.3: 真实交易成本计算（印花税0.1% + 佣金万2.5 + 滑点0.03%）
    df['transaction_cost'] = 0.0
    df.loc[df['signal'] == 1, 'transaction_cost'] = 0.00025 + 0.0003  # 买入：佣金+滑点
    df.loc[df['signal'] == -1, 'transaction_cost'] = 0.001 + 0.00025 + 0.0003  # 卖出：印花税+佣金+滑点

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
