#!/usr/bin/env python3
"""
股票池筛选模块（简化版）
直接使用已有技术指标的股票作为股票池
"""

import pandas as pd
import psycopg2
import logging
from typing import List

from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def build_stock_pool() -> List[str]:
    """
    构建股票池
    
    由于stock_basic表为空，直接使用已有技术指标的股票
    
    Returns:
    --------
    List[str]
        股票代码列表
    """
    conn = psycopg2.connect(**DB_CONFIG)
    
    query = """
        WITH stock_stats AS (
            SELECT 
                k.ts_code,
                COUNT(*) as data_count,
                AVG(k.amount) as avg_amount,
                MAX(k.trade_date) as latest_date
            FROM kline_daily k
            INNER JOIN technical_indicators t 
                ON k.ts_code = t.ts_code AND k.trade_date = t.trade_date
            WHERE k.trade_date >= '20250101'
            GROUP BY k.ts_code
            HAVING COUNT(*) >= 30  -- 至少30个交易日数据
        )
        SELECT 
            ts_code,
            data_count,
            avg_amount,
            latest_date
        FROM stock_stats
        WHERE avg_amount >= 10000  -- 日均成交额 > 1000万（降低门槛）
        ORDER BY avg_amount DESC
        LIMIT 100
    """
    
    try:
        df = pd.read_sql(query, conn)
        conn.close()
        
        stock_pool = df['ts_code'].tolist()
        
        logger.info("=" * 80)
        logger.info("股票池构建完成")
        logger.info("=" * 80)
        logger.info(f"股票数量: {len(stock_pool)}")
        logger.info(f"平均数据量: {df['data_count'].mean():.0f}天")
        logger.info(f"平均日成交额: {df['avg_amount'].mean()/100000:.2f}亿元")
        logger.info(f"最新数据日期: {df['latest_date'].max()}")
        logger.info("=" * 80)
        
        # 打印前10只股票
        logger.info("\n前10只股票:")
        for i, row in df.head(10).iterrows():
            logger.info(f"  {row['ts_code']}: 数据{row['data_count']}天, 日均成交{row['avg_amount']/100000:.2f}亿")
        
        return stock_pool
        
    except Exception as e:
        logger.error(f"构建股票池失败: {e}")
        conn.close()
        return []


if __name__ == '__main__':
    # 测试
    pool = build_stock_pool()
    print(f"\n股票池总数: {len(pool)}")
    print(f"股票池: {pool[:20]}")
