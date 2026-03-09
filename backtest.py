"""
回测引擎：模拟交易、计算收益、统计指标
"""

import pandas as pd
import numpy as np
from datetime import datetime
from config import BACKTEST_CONFIG


class BacktestEngine:
    """回测引擎"""

    def __init__(self, initial_capital=None):
        self.initial_capital = initial_capital or BACKTEST_CONFIG['initial_capital']
        self.cash = self.initial_capital
        self.positions = {}  # {ts_code: {'shares': int, 'avg_price': float}}
        self.trades = []     # 交易记录
        self.daily_values = []  # 每日账户价值

    def calculate_transaction_cost(self, price, shares, is_buy=True):
        """
        计算交易成本

        买入：佣金0.025% + 滑点0.2%
        卖出：佣金0.075% + 印花税0.05% + 滑点0.2%
        """
        amount = price * shares

        if is_buy:
            commission = amount * BACKTEST_CONFIG['commission_buy']
            slippage = amount * BACKTEST_CONFIG['slippage']
            total_cost = commission + slippage
        else:
            commission = amount * BACKTEST_CONFIG['commission_sell']
            stamp_tax = amount * BACKTEST_CONFIG['stamp_tax']
            slippage = amount * BACKTEST_CONFIG['slippage']
            total_cost = commission + stamp_tax + slippage

        return total_cost

    def buy(self, ts_code, date, price, shares, atr):
        """执行买入"""
        if shares <= 0:
            return False

        amount = price * shares
        cost = self.calculate_transaction_cost(price, shares, is_buy=True)
        total_required = amount + cost

        # 检查资金是否足够
        if total_required > self.cash:
            # 资金不足，按可用资金重新计算股数
            available_for_stock = self.cash * 0.99  # 留1%缓冲
            shares = int((available_for_stock / (price * 1.003)) // BACKTEST_CONFIG['lot_size']) * BACKTEST_CONFIG['lot_size']

            if shares <= 0:
                return False

            amount = price * shares
            cost = self.calculate_transaction_cost(price, shares, is_buy=True)
            total_required = amount + cost

        # 执行买入
        self.cash -= total_required

        if ts_code in self.positions:
            # 加仓
            old_shares = self.positions[ts_code]['shares']
            old_avg_price = self.positions[ts_code]['avg_price']
            new_shares = old_shares + shares
            new_avg_price = (old_avg_price * old_shares + price * shares) / new_shares
            self.positions[ts_code] = {'shares': new_shares, 'avg_price': new_avg_price}
        else:
            # 新开仓
            self.positions[ts_code] = {'shares': shares, 'avg_price': price}

        # 记录交易
        self.trades.append({
            'date': date,
            'ts_code': ts_code,
            'action': 'BUY',
            'price': price,
            'shares': shares,
            'amount': amount,
            'cost': cost,
            'atr': atr,
            'cash_after': self.cash
        })

        return True

    def sell(self, ts_code, date, price, shares=None):
        """执行卖出"""
        if ts_code not in self.positions:
            return False

        # 如果未指定股数，则全部卖出
        if shares is None:
            shares = self.positions[ts_code]['shares']

        shares = min(shares, self.positions[ts_code]['shares'])

        if shares <= 0:
            return False

        amount = price * shares
        cost = self.calculate_transaction_cost(price, shares, is_buy=False)
        proceeds = amount - cost

        # 执行卖出
        self.cash += proceeds

        # 计算盈亏
        avg_price = self.positions[ts_code]['avg_price']
        pnl = (price - avg_price) * shares - cost - self.calculate_transaction_cost(avg_price, shares, is_buy=True)
        pnl_pct = pnl / (avg_price * shares) * 100

        # 更新持仓
        self.positions[ts_code]['shares'] -= shares
        if self.positions[ts_code]['shares'] <= 0:
            del self.positions[ts_code]

        # 记录交易
        self.trades.append({
            'date': date,
            'ts_code': ts_code,
            'action': 'SELL',
            'price': price,
            'shares': shares,
            'amount': amount,
            'cost': cost,
            'pnl': pnl,
            'pnl_pct': pnl_pct,
            'cash_after': self.cash
        })

        return True

    def get_portfolio_value(self, current_prices):
        """
        计算当前组合价值

        Parameters:
        -----------
        current_prices : dict
            {ts_code: current_price}
        """
        position_value = 0
        for ts_code, pos in self.positions.items():
            if ts_code in current_prices:
                position_value += pos['shares'] * current_prices[ts_code]

        total_value = self.cash + position_value
        return total_value

    def record_daily_value(self, date, current_prices):
        """记录每日账户价值"""
        total_value = self.get_portfolio_value(current_prices)
        self.daily_values.append({
            'date': date,
            'cash': self.cash,
            'position_value': total_value - self.cash,
            'total_value': total_value
        })

    def get_trades_df(self):
        """获取交易记录DataFrame"""
        return pd.DataFrame(self.trades)

    def get_daily_values_df(self):
        """获取每日价值DataFrame"""
        return pd.DataFrame(self.daily_values)

    def calculate_metrics(self):
        """计算回测指标"""
        if len(self.daily_values) == 0:
            return {}

        df_values = self.get_daily_values_df()
        df_values['returns'] = df_values['total_value'].pct_change()

        # 总收益率
        total_return = (df_values['total_value'].iloc[-1] / self.initial_capital - 1) * 100

        # 年化收益率
        days = len(df_values)
        annual_return = ((df_values['total_value'].iloc[-1] / self.initial_capital) ** (252 / days) - 1) * 100

        # 最大回撤
        cummax = df_values['total_value'].cummax()
        drawdown = (df_values['total_value'] - cummax) / cummax * 100
        max_drawdown = drawdown.min()

        # Calmar Ratio
        calmar_ratio = annual_return / abs(max_drawdown) if max_drawdown != 0 else 0

        # 夏普比率
        if len(df_values) > 1:
            sharpe_ratio = df_values['returns'].mean() / df_values['returns'].std() * (252 ** 0.5) if df_values['returns'].std() > 0 else 0
        else:
            sharpe_ratio = 0

        # 胜率
        df_trades = self.get_trades_df()
        if len(df_trades) > 0:
            sell_trades = df_trades[df_trades['action'] == 'SELL']
            if len(sell_trades) > 0:
                win_rate = (sell_trades['pnl'] > 0).sum() / len(sell_trades) * 100
                avg_win = sell_trades[sell_trades['pnl'] > 0]['pnl'].mean() if (sell_trades['pnl'] > 0).any() else 0
                avg_loss = sell_trades[sell_trades['pnl'] < 0]['pnl'].mean() if (sell_trades['pnl'] < 0).any() else 0
            else:
                win_rate = 0
                avg_win = 0
                avg_loss = 0
        else:
            win_rate = 0
            avg_win = 0
            avg_loss = 0

        metrics = {
            'total_return': total_return,
            'annual_return': annual_return,
            'max_drawdown': max_drawdown,
            'calmar_ratio': calmar_ratio,
            'sharpe_ratio': sharpe_ratio,
            'win_rate': win_rate,
            'avg_win': avg_win,
            'avg_loss': avg_loss,
            'total_trades': len(df_trades),
            'final_value': df_values['total_value'].iloc[-1]
        }

        return metrics


def run_backtest(data_dict, params, initial_capital=None):
    """
    运行回测

    Parameters:
    -----------
    data_dict : dict
        {ts_code: DataFrame with signals and indicators}
    params : dict
        {'theta_buy', 'theta_sell', 'alpha_vol', 'R'}
    initial_capital : float, optional

    Returns:
    --------
    BacktestEngine
    """
    engine = BacktestEngine(initial_capital)

    # 获取所有交易日期
    all_dates = set()
    for df in data_dict.values():
        all_dates.update(df.index)
    all_dates = sorted(all_dates)

    # 逐日模拟
    for date in all_dates:
        current_prices = {}

        # 收集当日价格
        for ts_code, df in data_dict.items():
            if date in df.index:
                current_prices[ts_code] = df.loc[date, 'close']

        # 处理卖出信号（先卖后买）
        for ts_code, df in data_dict.items():
            if date in df.index and ts_code in engine.positions:
                if df.loc[date, 'sell_signal']:
                    price = df.loc[date, 'close']
                    engine.sell(ts_code, date, price)

        # 处理买入信号
        for ts_code, df in data_dict.items():
            if date in df.index:
                if df.loc[date, 'buy_signal'] and df.loc[date, 'target_shares'] > 0:
                    price = df.loc[date, 'close']
                    shares = int(df.loc[date, 'target_shares'])
                    atr = df.loc[date, 'ATR_14']
                    engine.buy(ts_code, date, price, shares, atr)

        # 记录每日价值
        engine.record_daily_value(date, current_prices)

    return engine
