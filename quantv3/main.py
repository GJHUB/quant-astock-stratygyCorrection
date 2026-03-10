#!/usr/bin/env python3
"""
主程序
完整执行流程
"""

import logging
import sys
from datetime import datetime

from config import DATASET_CONFIG, STRATEGY_PARAMS
from stock_pool import build_stock_pool
from data_loader import load_multiple_stocks
from optimizer import optimize_parameters
from backtest_engine import run_backtest
from report_generator import generate_report

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """
    主程序：完整执行流程
    """
    logger.info("=" * 80)
    logger.info("量化策略 v3.0 - 完整执行流程")
    logger.info("=" * 80)
    
    try:
        # 1. 构建股票池
        logger.info("\n[1/6] 构建股票池...")
        stock_pool = build_stock_pool()
        
        if len(stock_pool) == 0:
            logger.error("股票池为空，退出")
            return
        
        # 2. 划分数据集
        logger.info("\n[2/6] 划分数据集...")
        train_config = DATASET_CONFIG['train']
        test_config = DATASET_CONFIG['test']
        logger.info(f"训练集: {train_config['start_date']} - {train_config['end_date']}")
        logger.info(f"测试集: {test_config['start_date']} - {test_config['end_date']}")
        
        # 3. 加载训练集数据
        logger.info("\n[3/6] 加载训练集数据...")
        train_data = load_multiple_stocks(
            stock_pool[:20],  # 使用前20只股票进行训练
            train_config['start_date'],
            train_config['end_date']
        )
        
        if len(train_data) == 0:
            logger.error("无法加载训练集数据，退出")
            return
        
        # 4. 参数优化
        logger.info("\n[4/6] 参数优化（遗传算法）...")
        logger.info("注意：参数优化需要较长时间，请耐心等待...")
        
        try:
            best_params = optimize_parameters(train_data)
        except Exception as e:
            logger.warning(f"参数优化失败: {e}")
            logger.info("使用默认参数继续...")
            best_params = STRATEGY_PARAMS
        
        # 5. 加载测试集数据
        logger.info("\n[5/6] 加载测试集数据并运行回测...")
        test_data = load_multiple_stocks(
            stock_pool[:20],  # 使用相同的股票进行测试
            test_config['start_date'],
            test_config['end_date']
        )
        
        if len(test_data) == 0:
            logger.error("无法加载测试集数据，退出")
            return
        
        # 运行回测
        results = run_backtest(test_data, best_params)
        
        # 6. 生成报告
        logger.info("\n[6/6] 生成回测报告...")
        generate_report(best_params, results)
        
        logger.info("\n" + "=" * 80)
        logger.info("✅ 全部完成！")
        logger.info("=" * 80)
        logger.info(f"\n回测报告已生成，请查看 ./reports/ 目录")
        logger.info(f"- 回测报告: ./reports/backtest_report.md")
        logger.info(f"- 净值曲线: ./reports/equity_curve.png")
        
    except Exception as e:
        logger.error(f"执行失败: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
