#!/usr/bin/env python3
"""
数据加载模块
从PostgreSQL数据库加载股票数据和技术指标
"""

import pandas as pd
import psycopg2
from typing import List, Optional
import logging

from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """获取数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def load_stock_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    加载单只股票的K线数据和技术指标
    
    Parameters:
    -----------
    ts_code : str
        股票代码
    start_date : str
        开始日期 (YYYYMMDD)
    end_date : str
        结束日期 (YYYYMMDD)
    
    Returns:
    --------
    pd.DataFrame
        包含K线数据和技术指标的DataFrame
    """
    conn = get_db_connection()
    
    query = """
        SELECT 
            k.trade_date,
            k.open,
            k.high,
            k.low,
            k.close,
            k.vol,
            k.amount,
            t.sma5,
            t.sma10,
            t.sma20,
            t.sma60,
            t.sma200,
            t.vol_sma5,
            t.vol_sma10,
            t.vol_sma20,
            t.bias5,
            t.bias10,
            t.bias20,
            t.bias60,
            t.rsi6,
            t.rsi12,
            t.rsi14,
            t.rsi24,
            t.macd_dif,
            t.macd_dea,
            t.macd_hist,
            t.boll_upper,
            t.boll_mid,
            t.boll_lower,
            t.boll_width,
            t.atr14,
            t.atr20,
            t.kdj_k,
            t.kdj_d,
            t.kdj_j,
            t.volume_ratio
        FROM kline_daily k
        LEFT JOIN technical_indicators t 
            ON k.ts_code = t.ts_code AND k.trade_date = t.trade_date
        WHERE k.ts_code = %s
          AND k.trade_date >= %s
          AND k.trade_date <= %s
        ORDER BY k.trade_date
    """
    
    df = pd.read_sql(query, conn, params=(ts_code, start_date, end_date))
    conn.close()
    
    if len(df) == 0:
        logger.warning(f"{ts_code}: 无数据")
        return None
    
    # 转换日期格式
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df.set_index('trade_date', inplace=True)
    
    return df


def load_multiple_stocks(stock_pool: List[str], start_date: str, end_date: str) -> dict:
    """
    加载多只股票的数据
    
    Parameters:
    -----------
    stock_pool : List[str]
        股票代码列表
    start_date : str
        开始日期
    end_date : str
        结束日期
    
    Returns:
    --------
    dict
        {ts_code: DataFrame}
    """
    data_dict = {}
    
    for i, ts_code in enumerate(stock_pool, 1):
        logger.info(f"[{i}/{len(stock_pool)}] 加载 {ts_code}...")
        df = load_stock_data(ts_code, start_date, end_date)
        if df is not None and len(df) > 0:
            data_dict[ts_code] = df
    
    logger.info(f"✅ 成功加载 {len(data_dict)}/{len(stock_pool)} 只股票")
    
    return data_dict


def load_stock_basic_info(ts_code: str) -> dict:
    """
    加载股票基本信息
    
    Parameters:
    -----------
    ts_code : str
        股票代码
    
    Returns:
    --------
    dict
        股票基本信息
    """
    conn = get_db_connection()
    
    query = """
        SELECT ts_code, name, industry, area, market, list_date, list_status
        FROM stock_basic
        WHERE ts_code = %s
    """
    
    df = pd.read_sql(query, conn, params=(ts_code,))
    conn.close()
    
    if len(df) == 0:
        return None
    
    return df.iloc[0].to_dict()


def load_financial_data(ts_code: str, end_date: str) -> Optional[dict]:
    """
    加载最新财务数据
    
    Parameters:
    -----------
    ts_code : str
        股票代码
    end_date : str
        截止日期
    
    Returns:
    --------
    dict
        财务指标
    """
    conn = get_db_connection()
    
    query = """
        SELECT ts_code, end_date, roe, eps, netprofit_yoy
        FROM fina_indicator
        WHERE ts_code = %s
          AND end_date <= %s
        ORDER BY end_date DESC
        LIMIT 1
    """
    
    df = pd.read_sql(query, conn, params=(ts_code, end_date))
    conn.close()
    
    if len(df) == 0:
        return None
    
    return df.iloc[0].to_dict()


def load_market_cap(ts_code: str, trade_date: str) -> Optional[float]:
    """
    加载市值数据
    
    Parameters:
    -----------
    ts_code : str
        股票代码
    trade_date : str
        交易日期
    
    Returns:
    --------
    float
        总市值（万元）
    """
    conn = get_db_connection()
    
    query = """
        SELECT total_mv
        FROM daily_basic
        WHERE ts_code = %s
          AND trade_date = %s
    """
    
    df = pd.read_sql(query, conn, params=(ts_code, trade_date))
    conn.close()
    
    if len(df) == 0:
        return None
    
    return df.iloc[0]['total_mv']


def load_north_flow(trade_date: str) -> Optional[float]:
    """
    加载北向资金流入数据
    
    Parameters:
    -----------
    trade_date : str
        交易日期
    
    Returns:
    --------
    float
        北向资金净流入（亿元）
    """
    conn = get_db_connection()
    
    query = """
        SELECT north_money
        FROM moneyflow_hsgt
        WHERE trade_date = %s
    """
    
    df = pd.read_sql(query, conn, params=(trade_date,))
    conn.close()
    
    if len(df) == 0:
        return 0.0
    
    return df.iloc[0]['north_money']
