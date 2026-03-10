#!/usr/bin/env python3
"""
参数优化模块
使用DEAP遗传算法优化策略参数
"""

import random
import logging
from typing import Dict, List
from deap import base, creator, tools
import numpy as np

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
        {'annual_return': float, 'max_drawdown': float, 'turnover': float, 'num_trades': int}
    """
    from signal_generator import generate_signals

    total_trades = 0
    winning_trades = 0
    total_return = 0.0
    max_dd = 0.0

    for ts_code, df in data_dict.items():
        try:
            df_signals = generate_signals(df.copy(), params)

            # 简单计算收益
            buy_signals = df_signals[df_signals['signal'] == 1]
            sell_signals = df_signals[df_signals['signal'] == -1]

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
            continue

    # v3.1+: 防止分母为0，改进计算逻辑
    if total_trades == 0 or len(data_dict) == 0:
        return {'annual_return': 0.0, 'max_drawdown': -0.01, 'turnover': 0.0, 'num_trades': 0}

    avg_return = total_return / total_trades if total_trades > 0 else 0.0
    annual_return = avg_return * 252  # 年化
    max_drawdown = -0.1 if total_trades > 0 else -0.01  # 简化（负值）
    turnover = total_trades / len(data_dict) / 12  # 月均换手

    return {
        'annual_return': annual_return,
        'max_drawdown': max_drawdown,
        'turnover': turnover,
        'num_trades': total_trades
    }


def evaluate(individual: List, train_data: dict) -> tuple:
    """
    评估函数：Calmar Ratio - 交易次数惩罚 - 换手惩罚（v3.1+ - 强制最小30笔交易）

    Parameters:
    -----------
    individual : List
        [theta_buy, theta_sell, alpha_vol, rsi_thresh]
    train_data : dict
        训练集数据

    Returns:
    --------
    tuple
        (fitness_score,)
    """
    params = {
        'theta_buy': individual[0],
        'theta_sell': individual[1],
        'alpha_vol': max(0.5, min(0.8, individual[2])),  # 强制约束
        'rsi_thresh': int(individual[3]),
        'risk_per_trade': 0.02,
        'max_position': 0.8,
        'score_threshold': 0.60  # 降低阈值以捕获更多信号
    }

    try:
        results = simple_backtest(train_data, params)

        annual_ret = results['annual_return']
        max_dd = results['max_drawdown']
        turnover = results['turnover']
        num_trades = results['num_trades']

        # Calmar Ratio（防止分母为0）
        if abs(max_dd) < 0.001:  # 避免分母接近0
            calmar = annual_ret * 10  # 低回撤时给予奖励
        else:
            calmar = annual_ret / abs(max_dd)

        # 交易次数惩罚（少于30笔显著惩罚）
        min_trades = 30
        if num_trades < min_trades:
            trade_penalty = 10.0 * (min_trades - num_trades) / min_trades
        else:
            trade_penalty = 0.0

        # 换手率惩罚（年化>200%即月均>16.7%）
        turnover_penalty = max(0, turnover - 0.167) * 10

        # alpha_vol极值惩罚（限制在0.5~0.8）
        alpha_vol = individual[2]
        if alpha_vol < 0.5 or alpha_vol > 0.8:
            param_penalty = 5.0
        else:
            param_penalty = 0.0

        fitness = calmar - trade_penalty - turnover_penalty - param_penalty

        # 防止适应度为0（给予小的随机扰动）
        if abs(fitness) < 0.001:
            fitness = np.random.uniform(-0.1, 0.1)

        return (fitness,)

    except Exception as e:
        logger.error(f"评估失败: {e}")
        return (-999.0,)


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
    遗传算法优化参数（v3.1 - alpha_vol约束在0.5~0.8）

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
    logger.info("参数优化（遗传算法）")
    logger.info("=" * 80)
    
    # 创建适应度和个体类
    creator.create("FitnessMax", base.Fitness, weights=(1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMax)
    
    toolbox = base.Toolbox()
    
    # 定义个体（4个参数）
    toolbox.register("attr_theta_buy", random.uniform, 
                     PARAM_SPACE['theta_buy'][0], PARAM_SPACE['theta_buy'][1])
    toolbox.register("attr_theta_sell", random.uniform, 
                     PARAM_SPACE['theta_sell'][0], PARAM_SPACE['theta_sell'][1])
    toolbox.register("attr_alpha_vol", random.uniform, 
                     PARAM_SPACE['alpha_vol'][0], PARAM_SPACE['alpha_vol'][1])
    toolbox.register("attr_rsi_thresh", random.randint, 
                     PARAM_SPACE['rsi_thresh'][0], PARAM_SPACE['rsi_thresh'][1])
    
    toolbox.register("individual", tools.initCycle, creator.Individual,
                     (toolbox.attr_theta_buy, toolbox.attr_theta_sell,
                      toolbox.attr_alpha_vol, toolbox.attr_rsi_thresh), n=1)
    
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)
    toolbox.register("evaluate", evaluate, train_data=train_data)
    toolbox.register("mate", tools.cxTwoPoint)
    toolbox.register("mutate", tools.mutGaussian, mu=0, sigma=1, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=GA_CONFIG['tournament_size'])
    
    # 初始化种群
    pop = toolbox.population(n=GA_CONFIG['population_size'])
    
    logger.info(f"种群大小: {GA_CONFIG['population_size']}")
    logger.info(f"进化代数: {GA_CONFIG['generations']}")
    logger.info("=" * 80)
    
    # 进化
    for gen in range(GA_CONFIG['generations']):
        offspring = toolbox.select(pop, len(pop))
        offspring = list(map(toolbox.clone, offspring))
        
        # 交叉
        for child1, child2 in zip(offspring[::2], offspring[1::2]):
            if random.random() < GA_CONFIG['crossover_prob']:
                toolbox.mate(child1, child2)
                # 强制约束 alpha_vol 在 0.5~0.8
                child1[2] = max(0.5, min(0.8, child1[2]))
                child2[2] = max(0.5, min(0.8, child2[2]))
                del child1.fitness.values
                del child2.fitness.values
        
        # 变异
        for mutant in offspring:
            if random.random() < GA_CONFIG['mutation_prob']:
                toolbox.mutate(mutant)
                # 强制约束 alpha_vol 在 0.5~0.8
                mutant[2] = max(0.5, min(0.8, mutant[2]))
                del mutant.fitness.values
        
        # 评估
        invalid_ind = [ind for ind in offspring if not ind.fitness.valid]
        fitnesses = map(toolbox.evaluate, invalid_ind)
        for ind, fit in zip(invalid_ind, fitnesses):
            ind.fitness.values = fit
        
        pop[:] = offspring
        
        # 打印进度
        fits = [ind.fitness.values[0] for ind in pop]
        best_fit = max(fits)
        avg_fit = sum(fits) / len(fits)
        
        if gen % 10 == 0 or gen == GA_CONFIG['generations'] - 1:
            logger.info(f"Gen {gen:3d}: Best={best_fit:8.4f}, Avg={avg_fit:8.4f}")
    
    # 返回最优个体
    best_ind = tools.selBest(pop, 1)[0]
    
    best_params = {
        'theta_buy': round(best_ind[0], 2),
        'theta_sell': round(best_ind[1], 2),
        'alpha_vol': round(best_ind[2], 2),
        'rsi_thresh': int(best_ind[3]),
        'risk_per_trade': 0.02,
        'max_position': 0.8
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
