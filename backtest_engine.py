#!/usr/bin/env python3
"""
回测引擎模块
使用简化的回测逻辑（不依赖Backtrader）
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict, List
from datetime import datetime

from config import BACKTEST_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def run_backtest(data_dict: dict, params: dict) -> dict:
    """
    运行回测（v3.1 - A股成本模型、T+1执行、停牌过滤）

    Parameters:
    -----------
    data_dict : dict
        {ts_code: DataFrame with signals}
    params : dict
        策略参数

    Returns:
    --------
    dict
        回测结果
    """
    from signal_generator import generate_signals

    logger.info("=" * 80)
    logger.info("回测引擎 v3.1 (移除政策和北向资金筛选)")
    logger.info("=" * 80)
    logger.info(f"股票数量: {len(data_dict)}")
    logger.info(f"初始资金: {BACKTEST_CONFIG['initial_cash']:,.0f}")
    logger.info(f"成本模型: 佣金{BACKTEST_CONFIG['commission']:.5f} + 印花税{BACKTEST_CONFIG['stamp_tax']:.3f}(卖) + 滑点{BACKTEST_CONFIG['slippage']:.3f}")
    logger.info(f"执行模式: T+1（信号延迟1天执行）")
    logger.info("=" * 80)

    # 初始化
    cash = BACKTEST_CONFIG['initial_cash']
    positions = {}  # {ts_code: {'shares': int, 'cost': float, 'buy_date': date}}
    trades = []
    equity_curve = []

    # 获取所有交易日期
    all_dates = set()
    for df in data_dict.values():
        all_dates.update(df.index)
    all_dates = sorted(list(all_dates))

    # 为每只股票生成信号
    signals_dict = {}
    for ts_code, df in data_dict.items():
        signals_dict[ts_code] = generate_signals(df.copy(), params)

    # 逐日回测
    for date in all_dates:
        # 计算当前权益
        equity = cash
        for ts_code, pos in positions.items():
            if ts_code in signals_dict:
                df = signals_dict[ts_code]
                if date in df.index:
                    current_price = df.loc[date, 'close']
                    # 停牌检测（成交量为0）
                    if df.loc[date, 'vol'] > 0:
                        equity += pos['shares'] * current_price
                    else:
                        equity += pos['shares'] * pos.get('last_price', current_price)

        equity_curve.append({
            'date': date,
            'equity': equity
        })

        # 处理卖出信号（T+1检查）
        for ts_code, pos in list(positions.items()):
            if ts_code in signals_dict:
                df = signals_dict[ts_code]
                if date in df.index:
                    # T+1限制：买入当天不能卖出
                    if (date - pos['buy_date']).days < 1:
                        continue

                    signal = df.loc[date, 'signal']
                    # 停牌检测
                    if df.loc[date, 'vol'] == 0:
                        continue

                    if signal == -1:  # 卖出
                        sell_price = df.loc[date, 'close'] * (1 - BACKTEST_CONFIG['slippage'])  # 滑点
                        sell_value = pos['shares'] * sell_price
                        commission = sell_value * BACKTEST_CONFIG['commission']
                        stamp_tax = sell_value * BACKTEST_CONFIG['stamp_tax']
                        transfer_fee = sell_value * 0.00002  # 过户费
                        total_cost = commission + stamp_tax + transfer_fee
                        cash += sell_value - total_cost

                        profit = sell_value - pos['cost']
                        trades.append({
                            'ts_code': ts_code,
                            'date': date,
                            'type': 'sell',
                            'price': sell_price,
                            'shares': pos['shares'],
                            'value': sell_value,
                            'cost': total_cost,
                            'profit': profit
                        })

                        del positions[ts_code]

        # 处理买入信号
        for ts_code, df in signals_dict.items():
            if date in df.index:
                signal = df.loc[date, 'signal']
                # 停牌检测
                if df.loc[date, 'vol'] == 0:
                    continue

                if signal == 1 and ts_code not in positions:  # 买入
                    buy_price = df.loc[date, 'close'] * (1 + BACKTEST_CONFIG['slippage'])  # 滑点
                    target_shares = df.loc[date, 'target_shares']

                    if target_shares > 0:
                        buy_value = target_shares * buy_price
                        commission = buy_value * BACKTEST_CONFIG['commission']
                        transfer_fee = buy_value * 0.00002  # 过户费
                        total_cost = buy_value + commission + transfer_fee

                        if cash >= total_cost:
                            cash -= total_cost
                            positions[ts_code] = {
                                'shares': target_shares,
                                'cost': total_cost,
                                'buy_date': date,
                                'last_price': buy_price
                            }

                            trades.append({
                                'ts_code': ts_code,
                                'date': date,
                                'type': 'buy',
                                'price': buy_price,
                                'shares': target_shares,
                                'value': buy_value,
                                'cost': commission + transfer_fee,
                                'profit': 0
                            })
    
    # 计算回测指标
    equity_df = pd.DataFrame(equity_curve)
    equity_df['returns'] = equity_df['equity'].pct_change()

    final_equity = equity_df['equity'].iloc[-1]
    total_return = (final_equity - BACKTEST_CONFIG['initial_cash']) / BACKTEST_CONFIG['initial_cash']

    # 计算年化收益
    days = (equity_df['date'].iloc[-1] - equity_df['date'].iloc[0]).days
    annual_return = (1 + total_return) ** (365 / days) - 1 if days > 0 else 0

    # 计算最大回撤
    equity_df['cum_max'] = equity_df['equity'].cummax()
    equity_df['drawdown'] = (equity_df['equity'] - equity_df['cum_max']) / equity_df['cum_max']
    max_drawdown = equity_df['drawdown'].min()

    # 计算夏普比率
    sharpe_ratio = equity_df['returns'].mean() / equity_df['returns'].std() * np.sqrt(252) if equity_df['returns'].std() > 0 else 0

    # 计算换手率（月均）
    total_buy_trades = len([t for t in trades if t['type'] == 'buy'])
    months = days / 30 if days > 0 else 1
    turnover = total_buy_trades / len(data_dict) / months if months > 0 and len(data_dict) > 0 else 0

    # 计算胜率
    winning_trades = len([t for t in trades if t['type'] == 'sell' and t['profit'] > 0])
    total_sell_trades = len([t for t in trades if t['type'] == 'sell'])
    win_rate = winning_trades / total_sell_trades if total_sell_trades > 0 else 0

    # 计算平均盈亏
    avg_profit = np.mean([t['profit'] for t in trades if t['type'] == 'sell']) if total_sell_trades > 0 else 0
    avg_win = np.mean([t['profit'] for t in trades if t['type'] == 'sell' and t['profit'] > 0]) if winning_trades > 0 else 0
    avg_loss = np.mean([t['profit'] for t in trades if t['type'] == 'sell' and t['profit'] < 0]) if (total_sell_trades - winning_trades) > 0 else 0

    # 计算总交易成本
    total_cost = sum([t['cost'] for t in trades])

    results = {
        'initial_cash': BACKTEST_CONFIG['initial_cash'],
        'final_equity': final_equity,
        'total_return': total_return,
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'sharpe_ratio': sharpe_ratio,
        'turnover': turnover,
        'win_rate': win_rate,
        'total_trades': total_buy_trades,
        'total_sell_trades': total_sell_trades,
        'winning_trades': winning_trades,
        'avg_profit': avg_profit,
        'avg_win': avg_win,
        'avg_loss': avg_loss,
        'total_cost': total_cost,
        'equity_curve': equity_df,
        'trades': trades
    }

    logger.info("\n回测结果:")
    logger.info(f"  初始资金: {results['initial_cash']:,.0f}")
    logger.info(f"  最终权益: {results['final_equity']:,.0f}")
    logger.info(f"  总收益率: {results['total_return']:.2%}")
    logger.info(f"  年化收益率: {results['annual_return']:.2%}")
    logger.info(f"  最大回撤: {results['max_drawdown']:.2%}")
    logger.info(f"  夏普比率: {results['sharpe_ratio']:.2f}")
    logger.info(f"  换手率: {results['turnover']:.2f}/月")
    logger.info(f"  胜率: {results['win_rate']:.2%}")
    logger.info(f"  买入次数: {results['total_trades']}")
    logger.info(f"  卖出次数: {results['total_sell_trades']}")
    logger.info(f"  盈利次数: {results['winning_trades']}")
    logger.info(f"  平均盈亏: {results['avg_profit']:,.2f}")
    logger.info(f"  平均盈利: {results['avg_win']:,.2f}")
    logger.info(f"  平均亏损: {results['avg_loss']:,.2f}")
    logger.info(f"  总交易成本: {results['total_cost']:,.2f}")
    logger.info("=" * 80)

    return results


if __name__ == '__main__':
    # 测试
    from data_loader import load_multiple_stocks
    from stock_pool import build_stock_pool
    from config import STRATEGY_PARAMS
    
    pool = build_stock_pool()
    if len(pool) > 0:
        data = load_multiple_stocks(pool[:5], '20260101', '20260309')
        if len(data) > 0:
            results = run_backtest(data, STRATEGY_PARAMS)
