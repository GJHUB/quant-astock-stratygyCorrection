#!/usr/bin/env python3
"""
QuantV2 策略 WFO 调参脚本（优化版）
解决问题：
1. 冷启动问题：全局指标预计算
2. 过拟合问题：交易笔数惩罚机制
3. JSON序列化问题：numpy类型转换
"""

import sys
import json
import numpy as np
import pandas as pd
from datetime import datetime
from itertools import product

from data_loader import load_multiple_stocks_as_dataframe
from indicators import calculate_global_indicators
from signals import generate_signals
from position_sizing import add_position_sizing
from backtest import run_backtest
from config import WFO_PARAM_SPACE, BACKTEST_CONFIG


# ==========================================
# 补丁 1：JSON Numpy 类型转换器
# ==========================================
def convert_np_types(obj):
    """解决 TypeError: Object of type int64 is not JSON serializable"""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {k: convert_np_types(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [convert_np_types(i) for i in obj]
    return obj


# ==========================================
# 训练集：30只核心股票
# ==========================================
TRAINING_STOCKS = [
    # CPO/光模块子板块（8只）
    '300308.SZ',  # 中际旭创
    '300502.SZ',  # 新易盛
    '603083.SH',  # 剑桥科技
    '300548.SZ',  # 博创科技
    '300570.SZ',  # 太辰光
    '688498.SH',  # 源杰科技
    '002902.SZ',  # 铭普光磁
    '300620.SZ',  # 光库科技
    
    # 半导体/芯片子板块（8只）
    '300395.SZ',  # 菲利华
    '002371.SZ',  # 北方华创
    '688981.SH',  # 中芯国际
    '603501.SH',  # 韦尔股份
    '600460.SH',  # 士兰微
    '688099.SH',  # 晶晨股份
    '300782.SZ',  # 卓胜微
    '688608.SH',  # 恒玄科技
    
    # 人形机器人/国产算力子板块（8只）
    '688258.SH',  # 优必选
    '688017.SH',  # 绿的谐波
    '601689.SH',  # 拓普集团
    '603728.SH',  # 鸣志电器
    '688256.SH',  # 寒武纪
    '688041.SH',  # 海光信息
    '688047.SH',  # 龙芯中科
    '300474.SZ',  # 景嘉微
    
    # 液冷/海外算力子板块（6只）
    '601138.SH',  # 工业富联
    '002837.SZ',  # 英维克
    '300499.SZ',  # 高澜股份
    '300730.SZ',  # 曙光数创
    '000977.SZ',  # 浪潮信息
    '603019.SH',  # 中科曙光
]


# ====================================
# 简化回测评估（用于快速参数寻优）
# ==========================================
def evaluate_strategy_fast(df_slice, theta_buy, theta_sell, alpha_vol):
    """
    快速评估策略表现（简化版回测）
    
    改进：
    1. 添加交易笔数惩罚机制
    2. 使用向量化计算提高速度
    """
    df = df_slice.copy()
    
    # 生成买卖信号
    buy_condition = (
        (df['SMA_60'] > df['SMA_60_5d_ago']) & 
        (df['BIAS_20'] < -theta_buy) & 
        (df['volume'] < alpha_vol * df['Vol_SMA_10']) &
        (df['close'] > df['prev_close'])
    )
    
    sell_condition = (
        (df['BIAS_20'] > theta_sell) | 
        ((df['volume'] > 2.0 * df['Vol_SMA_10']) & (df['Upper_Shadow_Ratio'] > 0.6)) |
        (df['close'] < df['SMA_60'] * 0.95)
    )
    
    df['buy_signal'] = buy_condition
    df['sell_signal'] = sell_condition
    
    # 统计交易笔数
    total_trades = int(df['buy_signal'].sum())
    
    if total_trades == 0:
        return {
            'total_trades': 0,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'calmar_ratio': 0.0,
            'annual_return': 0.0,
            'max_drawdown': 0.0
        }
    
    # 简化收益计算：假设持有5天
    df['return_5d'] = df.groupby('ts_code')['close'].transform(
        lambda x: x.shift(-5) / x - 1
    )
    
    # 计算买入点的收益
    buy_returns = df[df['buy_signal']]['return_5d'].dropna()
    
    if len(buy_returns) == 0:
        return {
            'total_trades': total_trades,
            'win_rate': 0.0,
            'avg_return': 0.0,
            'calmar_ratio': 0.0,
            'annual_return': 0.0,
            'max_drawdown': 0.0
        }
    
    # 计算指标
    win_trades = int((buy_returns > 0).sum())
    win_rate = win_trades / len(buy_returns) if len(buy_returns) > 0 else 0.0
    avg_return = float(buy_returns.mean())
    max_dd = abs(float(buy_returns.min())) if len(buy_returns) > 0 else 1.0
    
    # ==========================================
    # 补丁 2：交易笔数惩罚机制
    # ==========================================
    if total_trades < 10:
        # 惩罚：交易次数太少，不具统计学意义
        calmar_ratio = 0.0
    else:
        calmar_ratio = avg_return / (max_dd + 1e-6)
    
    # 年化收益（简化计算）
    annual_return = avg_return * 252 / 5  # 假设持有5天
    
    return {
        'total_trades': total_trades,
        'win_rate': win_rate,
        'avg_return': avg_return,
        'calmar_ratio': calmar_ratio,
        'annual_return': annual_return,
        'max_drawdown': max_dd
    }


# ==========================================
# WFO 主执行逻辑
# ==========================================
def run_wfo_optimization(df_all, wfo_windows):
    """
    运行 Walk-Forward Optimization
    
    关键改进：
    1. 全局指标预计算（解决冷启动）
    2. 交易笔数惩罚（解决过拟合）
    3. 放宽参数空间（增加交易频率）
    """
    print("=" * 80)
    print("开始 Walk-Forward Optimization（优化版）")
    print("=" * 80)
    
    # ==========================================
    # 补丁 3：全局指标预计算
    # ==========================================
    print("\n正在进行全局指标预计算...")
    df_prepared = calculate_global_indicators(df_all)
    print(f"指标计算完成，共 {len(df_prepared)} 条记录")
    
    # 生成参数组合
    param_grid = {
        'theta_buy': np.arange(WFO_PARAM_SPACE['theta_buy'][0], 
                               WFO_PARAM_SPACE['theta_buy'][1] + WFO_PARAM_SPACE['theta_buy'][2]/2, 
                               WFO_PARAM_SPACE['theta_buy'][2]),
        'theta_sell': np.arange(WFO_PARAM_SPACE['theta_sell'][0], 
                                WFO_PARAM_SPACE['theta_sell'][1] + WFO_PARAM_SPACE['theta_sell'][2]/2, 
                                WFO_PARAM_SPACE['theta_sell'][2]),
        'alpha_vol': np.arange(WFO_PARAM_SPACE['alpha_vol'][0], 
                               WFO_PARAM_SPACE['alpha_vol'][1] + WFO_PARAM_SPACE['alpha_vol'][2]/2, 
                               WFO_PARAM_SPACE['alpha_vol'][2]),
    }
    
    keys, values = zip(*param_grid.items())
    param_combinations = [dict(zip(keys, v)) for v in product(*values)]
    print(f"参数空间大小: {len(param_combinations)}")
    
    wfo_results = []
    
    for idx, window in enumerate(wfo_windows):
        train_start, train_end = window['train']
        test_start, test_end = window['test']
        
        print(f"\n{'='*80}")
        print(f"窗口 {idx + 1}/{len(wfo_windows)}")
        print(f"{'='*80}")
        print(f"训练集: {train_start} - {train_end}")
        print(f"测试集: {test_start} - {test_end}")
        
        # 切分训练集（此时已包含完整指标，无冷启动问题）
        df_train = df_prepared[
            (df_prepared['trade_date'] >= train_start) & 
            (df_prepared['trade_date'] <= train_end)
        ].copy()
        
        print(f"训练集数据量: {len(df_train)} 条")
        
        best_params = None
        best_calmar = -1.0
        best_metrics = {}
        
        # 训练集网格搜索
        print("\n开始参数优化...")
        for i, params in enumerate(param_combinations):
            if i % 50 == 0:
                print(f"  进度: {i}/{len(param_combinations)}")
            
            try:
                metrics = evaluate_strategy_fast(df_train, **params)
                
                # 只有 Calmar > 0（交易次数 >= 10 且有正收益）才会被记录
                if metrics['calmar_ratio'] > best_calmar:
                    best_calmar = metrics['calmar_ratio']
                    best_params = params
                    best_metrics = metrics
            except Exception as e:
                print(f"  参数 {params} 评估失败: {e}")
                continue
        
        # 测试集验证
        if best_params is not None:
            print(f"\n找到最佳参数:")
            print(f"  theta_buy: {best_params['theta_buy']}")
            print(f"  theta_sell: {best_params['theta_sell']}")
            print(f"  alpha_vol: {best_params['alpha_vol']}")
            print(f"训练集表现:")
            print(f"  Calmar Ratio: {best_calmar:.4f}")
            print(f"  交易笔数: {best_metrics['total_trades']}")
            print(f"  胜率: {best_metrics['win_rate']:.2%}")
            print(f"  平均收益: {best_metrics['avg_return']:.2%}")
            
            # 测试集验证
            df_test = df_prepared[
                (df_prepared['trade_date'] >= test_start) & 
                (df_prepared['trade_date'] <= test_end)
            ].copy()
            
            print(f"\n测试集数据量: {len(df_test)} 条")
            test_metrics = evaluate_strategy_fast(df_test, **best_params)
            
            print(f"测试集表现:")
            print(f"  Calmar Ratio: {test_metrics['calmar_ratio']:.4f}")
            print(f"  交易笔数: {test_metrics['total_trades']}")
            print(f"  胜率: {test_metrics['win_rate']:.2%}")
            print(f"  平均收益: {test_metrics['avg_return']:.2%}")
            
            wfo_results.append({
                'window': idx + 1,
                'train_period': f"{train_start} - {train_end}",
                'test_period': f"{test_start} - {test_end}",
                'best_params': best_params,
                'train_metrics': best_metrics,
                'test_metrics': test_metrics
            })
        else:
            print("\n警告：该窗口下所有参数的交易次数均不足10笔，无法找到有效解！")
            print("建议：进一步放宽参数空间或增加训练集长度")
    
    return {
        'wfo_results': wfo_results,
        'summary': calculate_wfo_summary(wfo_results)
    }


def calculate_wfo_summary(wfo_results):
    """计算WFO汇总统计"""
    if len(wfo_results) == 0:
        return {}
    
    test_calmars = [r['test_metrics']['calmar_ratio'] for r in wfo_results]
    test_returns = [r['test_metrics']['avg_return'] for r in wfo_results]
    test_trades = [r['test_metrics']['total_trades'] for r in wfo_results]
    
    summary = {
        'total_windows': len(wfo_results),
        'avg_test_calmar': float(np.mean(test_calmars)),
        'avg_test_return': float(np.mean(test_returns)),
        'avg_test_trades': float(np.mean(test_trades)),
        'best_window': max(wfo_results, key=lambda x: x['test_metrics']['calmar_ratio'])
    }
    
    return summary


def main():
    print("=" * 80)
    print("QuantV2 策略 WFO 调参（优化版）")
    print("=" * 80)
    print(f"训练股票数量: {len(TRAINING_STOCKS)}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 加载训练集数据（返回单个DataFrame）
    print("\n正在加载训练集数据...")
    df_all = load_multiple_stocks_as_dataframe(
        stock_list=TRAINING_STOCKS,
        start_date='20220101',  # 从2022年开始，支持24个月训练集
        end_date='20260228'
    )
    
    if len(df_all) == 0:
        print("错误：没有加载到任何数据")
        sys.exit(1)
    
    print(f"成功加载数据，共 {len(df_all)} 条记录")
    
    # WFO时间窗口（优化版：24个月训练集，6个月测试集）
    wfo_windows = [
        {'train': ('20220101', '20231231'), 'test': ('20240101', '20240630')},  # 24个月训练
        {'train': ('20220701', '20240630'), 'test': ('20240701', '20241231')},  # 24个月训练
        {'train': ('20230101', '20241231'), 'test': ('20250101', '20250630')},  # 24个月训练
        {'train': ('20230701', '20250630'), 'test': ('20250701', '20260228')},  # 24个月训练
    ]
    
    print(f"时间窗口数量: {len(wfo_windows)}")
    
    # 运行WFO优化
    wfo_results = run_wfo_optimization(df_all, wfo_windows)
    
    # ==========================================
    # 补丁 4：安全保存为 JSON
    # ==========================================
    output_file = f"wfo_training_results_v2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    safe_results = convert_np_types(wfo_results)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(safe_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")
    
    # 打印汇总
    summary = wfo_results.get('summary', {})
    print("\n" + "=" * 80)
    print("WFO 汇总结果")
    print("=" * 80)
    print(f"总窗口数: {summary.get('total_windows', 0)}")
    print(f"平均测试集 Calmar Ratio: {summary.get('avg_test_calmar', 0):.4f}")
    print(f"平均测试集收益: {summary.get('avg_test_return', 0):.2%}")
    print(f"平均测试集交易笔数: {summary.get('avg_test_trades', 0):.1f}")
    
    best_window = summary.get('best_window', {})
    if best_window:
        print(f"\n最佳窗口: 窗口 {best_window.get('window', 0)}")
        print(f"  测试期间: {best_window.get('test_period', '')}")
        print(f"  最佳参数: {best_window.get('best_params', {})}")
        print(f"  Calmar Ratio: {best_window.get('test_metrics', {}).get('calmar_ratio', 0):.4f}")
        print(f"  交易笔数: {best_window.get('test_metrics', {}).get('total_trades', 0)}")
    
    print("\n" + "=" * 80)
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == '__main__':
    main()
