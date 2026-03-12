#!/usr/bin/env python3
"""
参数优化模块
使用DEAP遗传算法优化策略参数
"""

import random
import logging
import time
from typing import Dict, List
from deap import base, creator, tools
import numpy as np
import pandas as pd

from config import PARAM_SPACE, GA_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def simple_backtest(data_dict: dict, params: dict) -> dict:
    """
    简化回测（用于参数优化，v3.1+ - 增加交易次数统计）

    Parameters:
    -----------
    data_dict : dict
        {ts_code: DataFrame}
    params : dict
        策略参数

    Returns:
    --------
    dict
        {'annual_return': float, 'max_drawdown': float, 'turnover': float, 'num_trades': int, 
         'avg_score': float, 'score_std': float}
    """
    from signal_generator import generate_signals

    total_trades = 0
    winning_trades = 0
    total_return = 0.0
    max_dd = 0.0
    all_scores = []  # v3.3: 收集所有股票的 score 用于统计
    
    # 添加详细的 score 日志
    log_detail = params.get('_log_detail', False)  # 通过参数控制是否打印详细日志

    for ts_code, df in data_dict.items():
        try:
            df_signals = generate_signals(df.copy(), params)

            # 简单计算收益
            buy_signals = df_signals[df_signals['signal'] == 1]
            sell_signals = df_signals[df_signals['signal'] == -1]

            # v3.3: 收集所有买入信号触发时的 score（而不是只看最后一天）
            if 'signal_score' in df_signals.columns:
                score_series = df_signals['signal_score'].dropna()
                if len(score_series) > 0:
                    stock_avg_score = float(score_series.mean())
                    stock_max_score = float(score_series.max())
                    stock_min_score = float(score_series.min())
                    
                    # 打印每只股票的 score 统计
                    if log_detail:
                        logger.info(f"  {ts_code}: score(avg/min/max)={stock_avg_score:.4f}/{stock_min_score:.4f}/{stock_max_score:.4f}, buy_signals={len(buy_signals)}")
                        
                        # v3.3: 打印每个交易日的 score 值（详细日志）
                        logger.info(f"  {ts_code} 每日 score 详情:")
                        for idx, row in df_signals.iterrows():
                            score_val = row['signal_score']
                            if not pd.isna(score_val):
                                trade_date = row.get('trade_date', idx)
                                signal = row['signal']
                                signal_str = '买入' if signal == 1 else ('卖出' if signal == -1 else '持有')
                                logger.info(f"    {trade_date}: score={score_val:.4f}, signal={signal_str}")
                    
                    # 收集买入信号时的 score
                    for idx in buy_signals.index:
                        score_at_buy = df_signals.loc[idx, 'signal_score']
                        if not pd.isna(score_at_buy):
                            all_scores.append(float(score_at_buy))

            if len(buy_signals) > 0:
                total_trades += len(buy_signals)
                # 简化：假设每次买入后5天卖出
                for idx in buy_signals.index:
                    buy_price = df_signals.loc[idx, 'close']
                    future_idx = df_signals.index.get_loc(idx) + 5
                    if future_idx < len(df_signals):
                        sell_price = df_signals.iloc[future_idx]['close']
                        ret = (sell_price - buy_price) / buy_price
                        total_return += ret
                        if ret > 0:
                            winning_trades += 1
        except Exception as e:
            if log_detail:
                logger.warning(f"  {ts_code}: 评估失败 - {e}")
            continue

    # v3.1+: 防止分母为0，改进计算逻辑
    if total_trades == 0 or len(data_dict) == 0:
        return {'annual_return': 0.0, 'max_drawdown': -0.01, 'turnover': 0.0, 'num_trades': 0,
                'avg_score': 0.0, 'score_std': 0.0}

    avg_return = total_return / total_trades if total_trades > 0 else 0.0
    annual_return = avg_return * 252  # 年化
    max_drawdown = -0.1 if total_trades > 0 else -0.01  # 简化（负值）
    turnover = total_trades / len(data_dict) / 12  # 月均换手

    # v3.3: 计算 score 统计
    import numpy as np
    avg_score = float(np.mean(all_scores)) if all_scores else 0.0
    score_std = float(np.std(all_scores)) if all_scores else 0.0

    return {
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'turnover': turnover,
        'num_trades': total_trades,
        'avg_score': avg_score,
        'score_std': score_std
    }


def evaluate(individual: List, train_data: dict) -> tuple:
    """
    评估函数：Calmar Ratio - 交易次数惩罚 - 换手惩罚（v3.3 - 10维优化）

    v3.3改进：扩展为10维联合优化（4个权重 + 6个原有参数）
    - individual[0:4]: w_trend, w_bias, w_vol, w_rsi（权重，自动归一化）
    - individual[4:10]: theta_buy, theta_sell, alpha_vol, rsi_thresh, score_threshold

    Returns
    -------
    tuple
        (fitness_score, num_trades, annual_return, max_drawdown, avg_score, score_std)
    """
    # v3.3: 10维参数解析（4个权重 + 6个原有参数）
    params = {
        # 权重参数（前4维，会在signal_generator中自动归一化）
        'w_trend': individual[0],
        'w_bias': individual[1],
        'w_vol': individual[2],
        'w_rsi': individual[3],

        # 原有参数（后6维）
        'theta_buy': individual[4],  # v3.3: 负值（-10 ~ -6）
        'theta_sell': individual[5],
        'alpha_vol': max(0.70, min(0.90, individual[6])),  # v3.3: 调整范围0.70~0.90
        'rsi_thresh': int(individual[7]),
        'score_threshold': max(0.40, min(0.60, individual[8])),  # v3.3: 调整范围0.40~0.60
        'risk_per_trade': 0.02,
        'max_position': 0.8,
        'min_amount': 30000000
    }

    try:
        results = simple_backtest(train_data, params)

        annual_ret = results['annual_return']
        max_dd = results['max_drawdown']
        turnover = results['turnover']
        num_trades = results['num_trades']
        avg_score = results.get('avg_score', 0.0)  # v3.3: 新增 score 统计
        score_std = results.get('score_std', 0.0)

        # Calmar Ratio（防止分母为0）
        if abs(max_dd) < 0.001:  # 避免分母接近0
            calmar = annual_ret * 10  # 低回撤时给予奖励
        else:
            calmar = annual_ret / abs(max_dd)

        # v3.2.1: 交易次数惩罚（平滑化，避免整代适应度塌缩到同一常数）
        min_trades = GA_CONFIG.get('min_trades', 20)
        if num_trades < min_trades:
            gap = (min_trades - num_trades) / max(min_trades, 1)
            trade_penalty = 4.0 * gap * gap
        else:
            trade_penalty = 0.0

        # v3.2: 换手率惩罚（年化>200%即月均>16.7%）
        turnover_penalty = max(0, turnover - 0.167) * 10

        # v3.3: alpha_vol极值惩罚（限制在0.70~0.90）
        alpha_vol = individual[6]
        if alpha_vol < 0.70 or alpha_vol > 0.90:
            param_penalty = 5.0
        else:
            param_penalty = 0.0

        # v3.3: score_threshold极值惩罚（限制在0.40~0.60）
        score_threshold = individual[8]
        if score_threshold < 0.40 or score_threshold > 0.60:
            param_penalty += 5.0

        fitness = calmar - trade_penalty - turnover_penalty - param_penalty

        # 防止适应度为0（给予小的随机扰动）
        if abs(fitness) < 0.001:
            fitness = np.random.uniform(-0.1, 0.1)

        return (fitness, float(num_trades), float(annual_ret), float(max_dd), float(avg_score), float(score_std))

    except Exception as e:
        logger.error(f"评估失败: {e}")
        return (-999.0, 0.0, 0.0, -1.0, 0.0, 0.0)


def optimize_parameters_wfo(train_data: dict, val_data: dict = None, n_windows: int = 3) -> Dict:
    """
    Walk-Forward优化（v3.1 - 至少3窗口WFO）

    Parameters:
    -----------
    train_data : dict
        训练集数据
    val_data : dict
        验证集数据（可选）
    n_windows : int
        WFO窗口数（至少3）

    Returns:
    --------
    dict
        最优参数
    """
    logger.info("=" * 80)
    logger.info(f"Walk-Forward优化（{n_windows}窗口）")
    logger.info("=" * 80)

    # 简化：直接在整个训练集上优化
    # 实际WFO需要时间序列切分，这里先实现单次优化
    return optimize_parameters(train_data)


def optimize_parameters(train_data: dict) -> Dict:
    """
    遗传算法优化参数（v3.3 - 10维联合优化）

    v3.3改进：扩展为10维联合优化
    - 4个权重参数：w_trend, w_bias, w_vol, w_rsi
    - 6个原有参数：theta_buy, theta_sell, alpha_vol, rsi_thresh, score_threshold

    Parameters:
    -----------
    train_data : dict
        训练集数据

    Returns:
    --------
    dict
        最优参数
    """
    logger.info("=" * 80)
    logger.info("参数优化（遗传算法 v3.3 - 10维联合优化）")
    logger.info("=" * 80)

    # 创建适应度和个体类
    # v3.3: 返回6个值 (fitness, num_trades, annual_return, max_drawdown, avg_score, score_std)
    # 仅第一维(适应度)参与优化；其余维度给极小权重用于携带日志观测值（避免0权重除零）
    creator.create("FitnessMax", base.Fitness, weights=(1.0, 1e-12, 1e-12, 1e-12, 1e-12, 1e-12))
    creator.create("Individual", list, fitness=creator.FitnessMax)

    toolbox = base.Toolbox()

    # 定义个体（v3.3: 10个参数 = 4个权重 + 6个原有参数）
    # 权重参数（前4维）
    toolbox.register("attr_w_trend", random.uniform,
                     PARAM_SPACE['w_trend'][0], PARAM_SPACE['w_trend'][1])
    toolbox.register("attr_w_bias", random.uniform,
                     PARAM_SPACE['w_bias'][0], PARAM_SPACE['w_bias'][1])
    toolbox.register("attr_w_vol", random.uniform,
                     PARAM_SPACE['w_vol'][0], PARAM_SPACE['w_vol'][1])
    toolbox.register("attr_w_rsi", random.uniform,
                     PARAM_SPACE['w_rsi'][0], PARAM_SPACE['w_rsi'][1])

    # 原有参数（后6维）
    toolbox.register("attr_theta_buy", random.uniform,
                     PARAM_SPACE['theta_buy'][0], PARAM_SPACE['theta_buy'][1])
    toolbox.register("attr_theta_sell", random.uniform,
                     PARAM_SPACE['theta_sell'][0], PARAM_SPACE['theta_sell'][1])
    toolbox.register("attr_alpha_vol", random.uniform,
                     PARAM_SPACE['alpha_vol'][0], PARAM_SPACE['alpha_vol'][1])
    toolbox.register("attr_rsi_thresh", random.randint,
                     PARAM_SPACE['rsi_thresh'][0], PARAM_SPACE['rsi_thresh'][1])
    toolbox.register("attr_score_threshold", random.uniform,
                     PARAM_SPACE['score_threshold'][0], PARAM_SPACE['score_threshold'][1])

    toolbox.register("individual", tools.initCycle, creator.Individual,
                     (toolbox.attr_w_trend, toolbox.attr_w_bias, toolbox.attr_w_vol, toolbox.attr_w_rsi,
                      toolbox.attr_theta_buy, toolbox.attr_theta_sell,
                      toolbox.attr_alpha_vol, toolbox.attr_rsi_thresh,
                      toolbox.attr_score_threshold), n=1)

    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate, train_data=train_data)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=GA_CONFIG['tournament_size'])

    # 初始化种群
    pop = toolbox.population(n=GA_CONFIG['population_size'])

    logger.info(f"种群大小: {GA_CONFIG['population_size']}")
    logger.info(f"进化代数: {GA_CONFIG['generations']}")
    logger.info(f"目标交易次数: >= {GA_CONFIG['min_trades']}")
    logger.info("=" * 80)

    prev_best_params = None
    optimize_start_ts = time.time()

    # 进化
    for gen in range(GA_CONFIG['generations']):
        gen_start_ts = time.time()
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))

        # 交叉
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < GA_CONFIG['crossover_prob']:
                toolbox.mate(child1, child2)
                # v3.3: 强制约束 alpha_vol 在 0.70~0.90（索引6）
                child1[6] = max(0.70, min(0.90, child1[6]))
                child2[6] = max(0.70, min(0.90, child2[6]))
                # v3.3: 强制约束 score_threshold 在 0.40~0.60（索引8）
                child1[8] = max(0.40, min(0.60, child1[8]))
                child2[8] = max(0.40, min(0.60, child2[8]))
                del child1.fitness.values
                del child2.fitness.values

        # 变异
        for mutant in offspring:
            if random.random() < GA_CONFIG['mutation_prob']:
                toolbox.mutate(mutant)
                # v3.3: 强制约束 alpha_vol 在 0.70~0.90（索引6）
                mutant[6] = max(0.70, min(0.90, mutant[6]))
                # v3.3: 强制约束 score_threshold 在 0.40~0.60（索引8）
                mutant[8] = max(0.40, min(0.60, mutant[8]))
                del mutant.fitness.values

        # 评估
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit

        pop[:] = offspring

        # 打印进度
        fits = [ind.fitness.values[0] for ind in pop]
        trade_counts = [ind.fitness.values[1] for ind in pop]
        annual_rets = [ind.fitness.values[2] for ind in pop]
        drawdowns = [ind.fitness.values[3] for ind in pop]
        avg_scores = [ind.fitness.values[4] for ind in pop]  # v3.3: score 统计
        score_stds = [ind.fitness.values[5] for ind in pop]

        best_fit = max(fits)
        avg_fit = sum(fits) / len(fits)
        best_trades = max(trade_counts) if trade_counts else 0.0
        avg_trades = sum(trade_counts) / len(trade_counts) if trade_counts else 0.0
        best_ann = max(annual_rets) if annual_rets else 0.0
        avg_ann = sum(annual_rets) / len(annual_rets) if annual_rets else 0.0
        min_dd = min(drawdowns) if drawdowns else 0.0
        best_score = max(avg_scores) if avg_scores else 0.0  # v3.3: 最佳 score
        avg_score = sum(avg_scores) / len(avg_scores) if avg_scores else 0.0

        gen_cost_sec = time.time() - gen_start_ts
        total_cost_sec = time.time() - optimize_start_ts

        if gen % 10 == 0 or gen == GA_CONFIG['generations'] - 1:
            best_ind_gen = tools.selBest(pop, 1)[0]
            best_params_gen = {
                'w_trend': round(best_ind_gen[0], 3),
                'w_bias': round(best_ind_gen[1], 3),
                'w_vol': round(best_ind_gen[2], 3),
                'w_rsi': round(best_ind_gen[3], 3),
                'theta_buy': round(best_ind_gen[4], 2),
                'theta_sell': round(best_ind_gen[5], 2),
                'alpha_vol': round(max(0.70, min(0.90, best_ind_gen[6])), 2),
                'rsi_thresh': int(best_ind_gen[7]),
                'score_threshold': round(max(0.40, min(0.60, best_ind_gen[8])), 2)
            }

            logger.info(
                f"Gen {gen:3d}: Best={best_fit:8.4f}, Avg={avg_fit:8.4f}, "
                f"Trades(best/avg)={best_trades:.1f}/{avg_trades:.1f}, "
                f"Ann(best/avg)={best_ann:.4f}/{avg_ann:.4f}, MinDD={min_dd:.4f}, "
                f"Score(best/avg)={best_score:.4f}/{avg_score:.4f}, "
                f"GenTime={gen_cost_sec:.2f}s, Total={total_cost_sec:.2f}s, Params={best_params_gen}"
            )
            
            # 打印每只股票的 score 详情（使用最佳参数重新评估）
            logger.info(f"  详细 score 统计（使用最佳参数）:")
            best_params_with_log = best_params_gen.copy()
            best_params_with_log['_log_detail'] = True
            best_params_with_log['risk_per_trade'] = 0.02
            best_params_with_log['max_position'] = 0.8
            best_params_with_log['min_amount'] = 30000000
            simple_backtest(train_data, best_params_with_log)
            
            if prev_best_params is not None:
                changes = []
                for k in best_params_gen:
                    if best_params_gen[k] != prev_best_params[k]:
                        changes.append(f"{k}:{prev_best_params[k]}->{best_params_gen[k]}")
                if changes:
                    logger.info("          参数变化: " + ", ".join(changes))
                else:
                    logger.info("          参数变化: 无")
            prev_best_params = best_params_gen

    # 返回最优个体
    best_ind = tools.selBest(pop, 1)[0]

    best_params = {
        'w_trend': round(best_ind[0], 3),
        'w_bias': round(best_ind[1], 3),
        'w_vol': round(best_ind[2], 3),
        'w_rsi': round(best_ind[3], 3),
        'theta_buy': round(best_ind[4], 2),
        'theta_sell': round(best_ind[5], 2),
        'alpha_vol': round(best_ind[6], 2),
        'rsi_thresh': int(best_ind[7]),
        'score_threshold': round(best_ind[8], 2),
        'risk_per_trade': 0.02,
        'max_position': 0.8,
        'min_amount': 30000000
    }

    logger.info("=" * 80)
    logger.info(f"✅ 最优参数: {best_params}")
    logger.info(f"   最优适应度: {best_ind.fitness.values[0]:.4f}")
    logger.info("=" * 80)

    return best_params


if __name__ == '__main__':
    # 测试
    from data_loader import load_multiple_stocks
    from stock_pool import build_stock_pool
    
    pool = build_stock_pool()
    if len(pool) > 0:
        data = load_multiple_stocks(pool[:5], '20250101', '20251231')
        if len(data) > 0:
            best_params = optimize_parameters(data)
            print(f"\n最优参数: {best_params}")
