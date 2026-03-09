"""
主入口：运行回测
"""

import sys
import json
from datetime import datetime
import pandas as pd

from config import DATA_CONFIG, STRATEGY_PARAMS, BACKTEST_CONFIG
from data_loader import select_stock_pool, load_multiple_stocks
from indicators import calculate_all_indicators
from signals import generate_signals
from position_sizing import add_position_sizing
from backtest import run_backtest
from wfo_optimizer import run_wfo


def run_simple_backtest(use_wfo=False):
    """
    运行简单回测（不使用WFO）
    """
    print("=" * 60)
    print("量化策略回测系统")
    print("=" * 60)

    # 1. 筛选股票池
    print("\n[1/5] 筛选股票池...")
    try:
        stock_pool = select_stock_pool()
        print(f"股票池: {len(stock_pool)} 只")
    except Exception as e:
        print(f"筛选股票池失败: {e}")
        print("使用测试股票池（前10只）")
        from data_loader import load_stock_list
        all_stocks = load_stock_list()
        stock_pool = all_stocks[:10]

    # 2. 加载数据
    print("\n[2/5] 加载股票数据...")
    data_dict = load_multiple_stocks(
        stock_pool,
        DATA_CONFIG['start_date'],
        DATA_CONFIG['end_date']
    )

    if len(data_dict) == 0:
        print("错误：没有加载到任何数据")
        return

    # 3. 计算指标和信号
    print("\n[3/5] 计算技术指标和交易信号...")
    for ts_code in data_dict:
        df = data_dict[ts_code]

        # 计算指标
        df = calculate_all_indicators(df)

        # 生成信号
        df = generate_signals(
            df,
            theta_buy=STRATEGY_PARAMS['theta_buy'],
            theta_sell=STRATEGY_PARAMS['theta_sell'],
            alpha_vol=STRATEGY_PARAMS['alpha_vol']
        )

        # 计算仓位
        df = add_position_sizing(
            df,
            total_capital=BACKTEST_CONFIG['initial_capital'],
            risk_per_trade=STRATEGY_PARAMS['R']
        )

        data_dict[ts_code] = df

    # 4. 运行回测
    print("\n[4/5] 运行回测...")
    engine = run_backtest(data_dict, STRATEGY_PARAMS)

    # 5. 输出结果
    print("\n[5/5] 生成回测报告...")
    metrics = engine.calculate_metrics()

    print("\n" + "=" * 60)
    print("回测结果")
    print("=" * 60)
    print(f"初始资金: ¥{BACKTEST_CONFIG['initial_capital']:,.0f}")
    print(f"最终资金: ¥{metrics['final_value']:,.0f}")
    print(f"总收益率: {metrics['total_return']:.2f}%")
    print(f"年化收益率: {metrics['annual_return']:.2f}%")
    print(f"最大回撤: {metrics['max_drawdown']:.2f}%")
    print(f"Calmar Ratio: {metrics['calmar_ratio']:.4f}")
    print(f"Sharpe Ratio: {metrics['sharpe_ratio']:.4f}")
    print(f"胜率: {metrics['win_rate']:.2f}%")
    print(f"总交易次数: {metrics['total_trades']}")
    print(f"平均盈利: ¥{metrics['avg_win']:,.2f}")
    print(f"平均亏损: ¥{metrics['avg_loss']:,.2f}")

    # 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 保存回测结果
    result_file = f'/tmp/quantv2_strategy/backtest_results_{timestamp}.json'
    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump({
            'config': {
                'initial_capital': BACKTEST_CONFIG['initial_capital'],
                'params': STRATEGY_PARAMS,
                'stock_pool_size': len(stock_pool)
            },
            'metrics': metrics
        }, f, indent=2, ensure_ascii=False)
    print(f"\n回测结果已保存: {result_file}")

    # 保存交易日志
    trades_df = engine.get_trades_df()
    if len(trades_df) > 0:
        trades_file = f'/tmp/quantv2_strategy/trades_log_{timestamp}.csv'
        trades_df.to_csv(trades_file, index=False, encoding='utf-8-sig')
        print(f"交易日志已保存: {trades_file}")

    return engine, metrics


def run_wfo_backtest():
    """
    运行Walk-Forward Optimization回测
    """
    print("=" * 60)
    print("Walk-Forward Optimization 回测系统")
    print("=" * 60)

    # 1. 筛选股票池
    print("\n[1/4] 筛选股票池...")
    try:
        stock_pool = select_stock_pool()
        print(f"股票池: {len(stock_pool)} 只")
    except Exception as e:
        print(f"筛选股票池失败: {e}")
        print("使用测试股票池（前10只）")
        from data_loader import load_stock_list
        all_stocks = load_stock_list()
        stock_pool = all_stocks[:10]

    # 2. 加载数据
    print("\n[2/4] 加载股票数据...")
    data_dict = load_multiple_stocks(
        stock_pool,
        DATA_CONFIG['start_date'],
        DATA_CONFIG['end_date']
    )

    if len(data_dict) == 0:
        print("错误：没有加载到任何数据")
        return

    # 3. 运行WFO
    print("\n[3/4] 运行Walk-Forward Optimization...")
    wfo_results = run_wfo(
        data_dict,
        DATA_CONFIG['start_date'],
        DATA_CONFIG['end_date']
    )

    # 4. 保存结果
    print("\n[4/4] 保存WFO结果...")
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    wfo_file = f'/tmp/quantv2_strategy/wfo_optimization_{timestamp}.json'

    with open(wfo_file, 'w', encoding='utf-8') as f:
        json.dump(wfo_results, f, indent=2, ensure_ascii=False, default=str)

    print(f"\nWFO结果已保存: {wfo_file}")

    # 打印汇总
    summary = wfo_results['summary']
    print("\n" + "=" * 60)
    print("WFO 汇总")
    print("=" * 60)
    print(f"总窗口数: {summary['total_windows']}")
    print(f"平均测试集Calmar: {summary['avg_test_calmar']:.4f}")
    print(f"平均测试集年化收益: {summary['avg_test_return']:.2f}%")
    print(f"平均测试集最大回撤: {summary['avg_test_drawdown']:.2f}%")

    return wfo_results


if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='量化策略回测系统')
    parser.add_argument('--wfo', action='store_true', help='使用Walk-Forward Optimization')
    parser.add_argument('--simple', action='store_true', help='运行简单回测（默认）')

    args = parser.parse_args()

    try:
        if args.wfo:
            run_wfo_backtest()
        else:
            run_simple_backtest()
    except KeyboardInterrupt:
        print("\n\n用户中断")
    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()
