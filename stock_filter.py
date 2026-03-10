#!/usr/bin/env python3
"""
股票过滤模块
每日从股票池筛选20-40只高质量股票
"""

import pandas as pd
import psycopg2
import logging
from typing import List

from config import DB_CONFIG, FILTER_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def filter_stocks(stock_pool: List[str], trade_date: str) -> List[str]:
    """
    每日过滤股票（20-40只）- v3.1版本

    筛选规则（已移除政策情绪和北向资金）：
    1. 流动性：成交量 > 0（非停牌）
    2. 趋势：SMA60向上
    3. 价格：Close > SMA200 * 0.9
    4. 质量：按成交额排序（优先流动性好的）

    Parameters:
    -----------
    stock_pool : List[str]
        股票池
    trade_date : str
        交易日期（YYYYMMDD）

    Returns:
    --------
    List[str]
        过滤后的股票列表
    """
    if len(stock_pool) == 0:
        logger.warning("股票池为空")
        return []
    
    conn = psycopg2.connect(**DB_CONFIG)
    
    # 构建股票代码列表
    stock_codes = "','".join(stock_pool)
    
    # v3.1: 移除政策和北向资金筛选，聚焦技术指标
    query = f"""
        SELECT
            k.ts_code,
            k.close,
            k.vol,
            k.amount,
            t.sma60,
            t.sma200
        FROM kline_daily k
        INNER JOIN technical_indicators t
            ON k.ts_code = t.ts_code AND k.trade_date = t.trade_date
        WHERE k.trade_date = '{trade_date}'
          AND k.ts_code IN ('{stock_codes}')
          AND k.vol > 0
          AND t.sma60 IS NOT NULL
          AND t.sma200 IS NOT NULL
          AND t.sma60 > (SELECT sma60 FROM technical_indicators
                         WHERE ts_code = k.ts_code
                         AND trade_date < k.trade_date
                         ORDER BY trade_date DESC LIMIT 1 OFFSET 4)
          AND k.close > t.sma200 * {FILTER_CONFIG['sma200_ratio']}
        ORDER BY k.amount DESC
        LIMIT {FILTER_CONFIG['target_size'][1]}
    """
    
    try:
        df = pd.read_sql(query, conn)
        conn.close()
        
        filtered_stocks = df['ts_code'].tolist()
        
        logger.info(f"✅ {trade_date}: 过滤后 {len(filtered_stocks)} 只股票")
        
        return filtered_stocks
        
    except Exception as e:
        logger.error(f"过滤股票失败: {e}")
        conn.close()
        return stock_pool[:FILTER_CONFIG['target_size'][1]]  # 失败时返回前N只


if __name__ == '__main__':
    # 测试
    from stock_pool import build_stock_pool
    
    pool = build_stock_pool()
    if len(pool) > 0:
        filtered = filter_stocks(pool, '20260306')
        print(f"\n过滤结果: {filtered[:10]}...")
