#!/usr/bin/env python3
"""
主程序
完整执行流程（v3.2）
"""

import logging
import sys
import argparse
import os
from datetime import datetime

from config import DATASET_CONFIG, STRATEGY_PARAMS
from stock_pool import build_stock_pool, get_training_stock_pool
from data_loader import load_multiple_stocks
from optimizer import optimize_parameters_wfo
from backtest_engine import run_backtest
from report_generator import generate_report
from signal_generator import generate_signals

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def log_stock_quant_metrics(data_dict: dict, params: dict, title: str = "训练集指标快照"):
    """打印每只股票的价格、核心技术指标、量化评分与信号统计（v3.3 - 增强score统计）"""
    logger.info("\n" + "=" * 80)
    logger.info(f"{title}（逐股）")
    
    # 统计日期范围
    if len(data_dict) > 0:
        all_dates = []
        for df in data_dict.values():
            if len(df) > 0:
                all_dates.extend(df.index.tolist())
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            logger.info(f"数据集日期范围: {str(min_date)[:10]} 至 {str(max_date)[:10]}")
            logger.info(f"股票数量: {len(data_dict)} 只")
    
    logger.info("字段: ts_code | trade_date | close | bias20 | rsi14 | macd_hist | score(last/avg/min/max) | buy_days | sell_days")
    logger.info("=" * 80)

    for ts_code, df in data_dict.items():
        try:
            sig = generate_signals(df.copy(), params)
            last = sig.iloc[-1]
            trade_date = str(sig.index[-1])[:10]
            close = float(last.get('close', 0) or 0)
            bias20 = float(last.get('bias20', 0) or 0)
            rsi14 = float(last.get('rsi14', 0) or 0)
            macd_hist = float(last.get('macd_hist', 0) or 0)

            # v3.3: 增强 score 统计 - 显示整个时间段的 score 分布
            score_series = sig['signal_score'].dropna()
            if len(score_series) > 0:
                score_last = float(score_series.iloc[-1])
                score_avg = float(score_series.mean())
                score_min = float(score_series.min())
                score_max = float(score_series.max())
            else:
                score_last = score_avg = score_min = score_max = float('nan')

            buy_days = int((sig['signal'] == 1).sum())
            sell_days = int((sig['signal'] == -1).sum())

            logger.info(
                f"{ts_code} | date={trade_date} | close={close:.4f} | bias20={bias20:.4f} | "
                f"rsi14={rsi14:.2f} | macd_hist={macd_hist:.4f} | "
                f"score(last/avg/min/max)={score_last:.4f}/{score_avg:.4f}/{score_min:.4f}/{score_max:.4f} | "
                f"buy_days={buy_days} | sell_days={sell_days}"
            )
        except Exception as e:
            logger.warning(f"{ts_code} 指标快照失败: {e}")


def main():
    """
    主程序：完整执行流程（v3.2）
    WFO训练 + OOS测试模式
    """
    parser = argparse.ArgumentParser(description='量化策略回测系统 v3.2')
    parser.add_argument('--version', type=str, default='v3.2', help='版本号')
    parser.add_argument('--skip-optimize', action='store_true', help='跳过参数优化')
    parser.add_argument('--oos-mode', type=str, default='primary',
                        choices=['primary', 'stress_test'],
                        help='OOS测试模式: primary(2025-2026) 或 stress_test(2021-2023)')
    parser.add_argument('--pool-size', type=int, default=None,
                        help='[已弃用] 股票池大小；当前版本默认使用训练/测试池全部可用股票')
    args = parser.parse_args()

    version = args.version
    output_dir = f'./result_{version}'
    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 80)
    logger.info(f"量化策略 {version} - 完整执行流程")
    logger.info("=" * 80)
    logger.info(f"输出目录: {output_dir}")
    logger.info("v3.2改进: 加权评分系统 + 交易次数优化 + 换手率控制")
    logger.info(f"全样本周期: {DATASET_CONFIG['full_period']['start_date']} - {DATASET_CONFIG['full_period']['end_date']}")
    logger.info(f"WFO配置: 训练{DATASET_CONFIG['wfo']['train_window_years']}年 + 验证{DATASET_CONFIG['wfo']['val_window_months']}个月")
    logger.info(f"OOS测试模式: {args.oos_mode}")
    if args.pool_size is not None:
        logger.info(f"收到 --pool-size={args.pool_size}，但当前版本已弃用该参数，将使用全部可用股票")
    logger.info("=" * 80)

    try:
        # 1. 加载训练集与测试集股票池
        logger.info("\n[1/6] 加载训练集与测试集股票池...")
        train_pool = get_training_stock_pool()
        test_pool = build_stock_pool()

        if len(train_pool) == 0:
            logger.error("训练集股票池为空，退出")
            return
        if len(test_pool) == 0:
            logger.error("测试集股票池为空，退出")
            return

        # 使用训练/测试池全部可用股票，不做人为数量截断
        logger.info(f"训练集股票数: {len(train_pool)}只（全部可用）")
        logger.info(f"测试集股票数: {len(test_pool)}只（全部可用）")

        # 2. 划分数据集（v3.2 - WFO模式）
        logger.info("\n[2/6] 划分数据集（WFO + OOS）...")
        full_period = DATASET_CONFIG['full_period']
        wfo_config = DATASET_CONFIG['wfo']
        oos_config = DATASET_CONFIG['oos_test'][args.oos_mode]

        logger.info(f"全样本周期: {full_period['start_date']} - {full_period['end_date']}")
        logger.info(f"WFO训练窗口: {wfo_config['train_window_years']}年")
        logger.info(f"WFO验证窗口: {wfo_config['val_window_months']}个月")
        logger.info(f"WFO滚动步长: {wfo_config['step_months']}个月")
        logger.info(f"OOS测试集: {oos_config['start_date']} - {oos_config['end_date']} ({oos_config['description']})")

        # 3. 加载WFO训练数据（全样本周期用于WFO）
        logger.info("\n[3/6] 加载WFO训练数据...")
        logger.info(f"加载周期: {full_period['start_date']} - {full_period['end_date']}")
        wfo_data = load_multiple_stocks(
            train_pool,
            full_period['start_date'],
            full_period['end_date']
        )

        if len(wfo_data) == 0:
            logger.error("无法加载WFO训练数据，退出")
            return

        logger.info(f"成功加载 {len(wfo_data)} 只股票数据")

        # 训练集逐股指标快照（用于诊断无交易问题）
        log_stock_quant_metrics(wfo_data, STRATEGY_PARAMS, title="训练集价格/技术指标/量化指标快照")

        # 4. 参数优化（WFO）
        logger.info("\n[4/6] 参数优化（Walk-Forward优化）...")
        logger.info("注意：参数优化需要较长时间，请耐心等待...")

        if args.skip_optimize:
            logger.info("跳过参数优化，使用默认参数")
            best_params = STRATEGY_PARAMS.copy()
            logger.info(f"本次运行参数: {best_params}")
        else:
            try:
                # WFO优化（至少3窗口）
                base_params = STRATEGY_PARAMS.copy()
                best_params = optimize_parameters_wfo(wfo_data, n_windows=3)
                logger.info("参数优化完成，本次运行参数变化如下：")
                for k in sorted(best_params.keys()):
                    old_v = base_params.get(k)
                    new_v = best_params.get(k)
                    if old_v != new_v:
                        logger.info(f"  {k}: {old_v} -> {new_v}")
                    else:
                        logger.info(f"  {k}: {new_v} (unchanged)")
            except Exception as e:
                logger.warning(f"参数优化失败: {e}")
                logger.info("使用默认参数继续...")
                best_params = STRATEGY_PARAMS.copy()

        # 5. 加载OOS测试集数据
        logger.info("\n[5/6] 加载OOS测试集数据并运行回测...")
        logger.info(f"OOS测试周期: {oos_config['start_date']} - {oos_config['end_date']}")
        oos_data = load_multiple_stocks(
            test_pool,
            oos_config['start_date'],
            oos_config['end_date']
        )

        if len(oos_data) == 0:
            logger.error("无法加载OOS测试集数据，退出")
            return

        logger.info(f"成功加载 {len(oos_data)} 只股票数据")

        # 运行回测
        results = run_backtest(oos_data, best_params)

        # 6. 生成报告
        logger.info("\n[6/6] 生成回测报告...")
        generate_report(best_params, results, output_dir, version)

        logger.info("\n" + "=" * 80)
        logger.info("✅ 全部完成！")
        logger.info("=" * 80)
        logger.info(f"\n回测报告已生成，请查看 {output_dir}/ 目录")
        logger.info(f"- 回测报告: {output_dir}/backtest_report_{version}.md")
        logger.info(f"- 净值曲线: {output_dir}/equity_curve_{version}.png")
        logger.info(f"\nOOS测试模式: {args.oos_mode}")
        logger.info(f"测试周期: {oos_config['start_date']} - {oos_config['end_date']}")

    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
