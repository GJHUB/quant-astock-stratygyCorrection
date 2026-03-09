"""
Walk-Forward Optimization (WFO) 优化器
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import itertools
import json

from config import WFO_CONFIG, WFO_PARAM_SPACE, BACKTEST_CONFIG
from indicators import calculate_all_indicators
from signals import generate_signals
from position_sizing import add_position_sizing
from backtest import run_backtest


def generate_param_combinations():
    """生成参数组合"""
    param_ranges = {}

    for param_name, (min_val, max_val, step) in WFO_PARAM_SPACE.items():
        param_ranges[param_name] = np.arange(min_val, max_val + step/2, step)

    # 生成所有组合
    keys = param_ranges.keys()
    values = param_ranges.values()
    combinations = [dict(zip(keys, v)) for v in itertools.product(*values)]

    return combinations


def split_train_test_periods(start_date, end_date, train_months=12, test_months=3):
    """
    切分训练集和测试集时间窗口

    Returns:
    --------
    list of tuples
        [(train_start, train_end, test_start, test_end), ...]
    """
    periods = []

    current_date = pd.to_datetime(start_date, format='%Y%m%d')
    end = pd.to_datetime(end_date, format='%Y%m%d')

    while True:
        train_start = current_date
        train_end = train_start + relativedelta(months=train_months)
        test_start = train_end
        test_end = test_start + relativedelta(months=test_months)

        if test_end > end:
            break

        periods.append((
            train_start.strftime('%Y%m%d'),
            train_end.strftime('%Y%m%d'),
            test_start.strftime('%Y%m%d'),
            test_end.strftime('%Y%m%d')
        ))

        # 滚动窗口向前移动test_months
        current_date = test_start

    return periods


def optimize_on_train_set(data_dict, train_start, train_end, param_combinations):
    """
    在训练集上优化参数

    Returns:
    --------
    dict
        最佳参数组合
    """
    print(f"\n训练集优化: {train_start} - {train_end}")
    print(f"参数组合数量: {len(param_combinations)}")

    best_params = None
    best_calmar = -999999

    for i, params in enumerate(param_combinations):
        if i % 50 == 0:
            print(f"  进度: {i}/{len(param_combinations)}")

        try:
            # 准备数据
            train_data = {}
            for ts_code, df in data_dict.items():
                df_train = df[(df.index >= train_start) & (df.index <= train_end)].copy()
                if len(df_train) < 100:
                    continue

                # 计算指标
                df_train = calculate_all_indicators(df_train)

                # 生成信号
                df_train = generate_signals(
                    df_train,
                    theta_buy=params['theta_buy'],
                    theta_sell=params['theta_sell'],
                    alpha_vol=params['alpha_vol']
                )

                # 计算仓位
                df_train = add_position_sizing(
                    df_train,
                    total_capital=BACKTEST_CONFIG['initial_capital'],
                    risk_per_trade=params['R']
                )

                train_data[ts_code] = df_train

            if len(train_data) == 0:
                continue

            # 运行回测
            engine = run_backtest(train_data, params)
            metrics = engine.calculate_metrics()

            calmar = metrics.get('calmar_ratio', -999999)

            if calmar > best_calmar:
                best_calmar = calmar
                best_params = params.copy()
                best_params['train_calmar'] = calmar
                best_params['train_metrics'] = metrics

        except Exception as e:
            print(f"  参数 {params} 优化失败: {e}")
            continue

    print(f"  最佳Calmar Ratio: {best_calmar:.4f}")
    print(f"  最佳参数: {best_params}")

    return best_params


def test_on_test_set(data_dict, test_start, test_end, best_params):
    """
    在测试集上验证参数

    Returns:
    --------
    dict
        测试集表现指标
    """
    print(f"\n测试集验证: {test_start} - {test_end}")

    try:
        # 准备数据
        test_data = {}
        for ts_code, df in data_dict.items():
            df_test = df[(df.index >= test_start) & (df.index <= test_end)].copy()
            if len(df_test) < 20:
                continue

            # 计算指标
            df_test = calculate_all_indicators(df_test)

            # 生成信号
            df_test = generate_signals(
                df_test,
                theta_buy=best_params['theta_buy'],
                theta_sell=best_params['theta_sell'],
                alpha_vol=best_params['alpha_vol']
            )

            # 计算仓位
            df_test = add_position_sizing(
                df_test,
                total_capital=BACKTEST_CONFIG['initial_capital'],
                risk_per_trade=best_params['R']
            )

            test_data[ts_code] = df_test

        if len(test_data) == 0:
            return None

        # 运行回测
        engine = run_backtest(test_data, best_params)
        metrics = engine.calculate_metrics()

        print(f"  测试集Calmar Ratio: {metrics.get('calmar_ratio', 0):.4f}")
        print(f"  测试集年化收益: {metrics.get('annual_return', 0):.2f}%")
        print(f"  测试集最大回撤: {metrics.get('max_drawdown', 0):.2f}%")

        return metrics

    except Exception as e:
        print(f"  测试集验证失败: {e}")
        return None


def run_wfo(data_dict, start_date, end_date):
    """
    运行Walk-Forward Optimization

    Returns:
    --------
    dict
        WFO结果
    """
    print("=" * 60)
    print("开始 Walk-Forward Optimization")
    print("=" * 60)
    sys.stdout.flush()

    # 生成参数组合
    param_combinations = generate_param_combinations()
    print(f"参数空间大小: {len(param_combinations)}")
    sys.stdout.flush()

    # 切分时间窗口
    periods = split_train_test_periods(
        start_date,
        end_date,
        train_months=WFO_CONFIG['train_months'],
        test_months=WFO_CONFIG['test_months']
    )
    print(f"时间窗口数量: {len(periods)}")
    sys.stdout.flush()

    wfo_results = []

    for i, (train_start, train_end, test_start, test_end) in enumerate(periods):
        print(f"\n{'='*60}")
        print(f"窗口 {i+1}/{len(periods)}")
        print(f"{'='*60}")
        sys.stdout.flush()

        # 训练集优化
        best_params = optimize_on_train_set(
            data_dict,
            train_start,
            train_end,
            param_combinations
        )

        if best_params is None:
            print("  训练集优化失败，跳过此窗口")
            continue

        # 测试集验证
        test_metrics = test_on_test_set(
            data_dict,
            test_start,
            test_end,
            best_params
        )

        if test_metrics is None:
            print("  测试集验证失败，跳过此窗口")
            continue

        # 保存结果
        wfo_results.append({
            'window': i + 1,
            'train_period': f"{train_start} - {train_end}",
            'test_period': f"{test_start} - {test_end}",
            'best_params': {
                'theta_buy': best_params['theta_buy'],
                'theta_sell': best_params['theta_sell'],
                'alpha_vol': best_params['alpha_vol'],
                'R': best_params['R']
            },
            'train_metrics': best_params.get('train_metrics', {}),
            'test_metrics': test_metrics
        })

    print("\n" + "=" * 60)
    print("WFO 完成")
    print("=" * 60)

    return {
        'wfo_results': wfo_results,
        'summary': calculate_wfo_summary(wfo_results)
    }


def calculate_wfo_summary(wfo_results):
    """计算WFO汇总统计"""
    if len(wfo_results) == 0:
        return {}

    test_calmars = [r['test_metrics'].get('calmar_ratio', 0) for r in wfo_results]
    test_returns = [r['test_metrics'].get('annual_return', 0) for r in wfo_results]
    test_drawdowns = [r['test_metrics'].get('max_drawdown', 0) for r in wfo_results]

    summary = {
        'total_windows': len(wfo_results),
        'avg_test_calmar': np.mean(test_calmars),
        'avg_test_return': np.mean(test_returns),
        'avg_test_drawdown': np.mean(test_drawdowns),
        'best_window': max(wfo_results, key=lambda x: x['test_metrics'].get('calmar_ratio', -999))
    }

    return summary
