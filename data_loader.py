#!/usr/bin/env python3
"""
数据加载模块
从PostgreSQL数据库加载股票数据和技术指标，支持AkShare fallback
"""

import pandas as pd
import psycopg2
from typing import List, Optional
import logging
import akshare as ak
import numpy as np

from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_db_connection():
    """获取数据库连接"""
    try:
        return psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logger.warning(f"数据库连接失败: {e}")
        return None


def load_stock_data(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    加载单只股票的K线数据和技术指标，支持AkShare fallback

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

    if conn is not None:
        try:
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

            if len(df) > 0:
                df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
                df.set_index('trade_date', inplace=True)
                return df
        except Exception as e:
            logger.warning(f"{ts_code}: 数据库加载失败 {e}")
            if conn:
                conn.close()

    # AkShare fallback
    logger.info(f"{ts_code}: 使用AkShare fallback")
    return load_from_akshare(ts_code, start_date, end_date)


def load_from_akshare(ts_code: str, start_date: str, end_date: str) -> pd.DataFrame:
    """
    从AkShare加载数据并计算技术指标
    """
    try:
        symbol = ts_code.split('.')[0]
        start = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}"
        end = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}"

        df = ak.stock_zh_a_hist(symbol=symbol, start_date=start, end_date=end, adjust="qfq")

        if df is None or len(df) == 0:
            return None

        df.rename(columns={
            '日期': 'trade_date',
            '开盘': 'open',
            '最高': 'high',
            '最低': 'low',
            '收盘': 'close',
            '成交量': 'vol',
            '成交额': 'amount'
        }, inplace=True)

        df['trade_date'] = pd.to_datetime(df['trade_date'])
        df.set_index('trade_date', inplace=True)

        # 计算技术指标
        df = calculate_indicators(df)

        return df
    except Exception as e:
        logger.error(f"{ts_code}: AkShare加载失败 {e}")
        return None


def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """计算技术指标"""
    # 均线
    df['sma5'] = df['close'].rolling(5).mean()
    df['sma10'] = df['close'].rolling(10).mean()
    df['sma20'] = df['close'].rolling(20).mean()
    df['sma60'] = df['close'].rolling(60).mean()
    df['sma200'] = df['close'].rolling(200).mean()

    # 成交量均线
    df['vol_sma5'] = df['vol'].rolling(5).mean()
    df['vol_sma10'] = df['vol'].rolling(10).mean()
    df['vol_sma20'] = df['vol'].rolling(20).mean()

    # 乖离率
    df['bias5'] = (df['close'] - df['sma5']) / df['sma5'] * 100
    df['bias10'] = (df['close'] - df['sma10']) / df['sma10'] * 100
    df['bias20'] = (df['close'] - df['sma20']) / df['sma20'] * 100
    df['bias60'] = (df['close'] - df['sma60']) / df['sma60'] * 100

    # RSI
    delta = df['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
    rs = gain / loss
    df['rsi14'] = 100 - (100 / (1 + rs))
    df['rsi6'] = df['rsi14']
    df['rsi12'] = df['rsi14']
    df['rsi24'] = df['rsi14']

    # MACD
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    df['macd_dif'] = ema12 - ema26
    df['macd_dea'] = df['macd_dif'].ewm(span=9).mean()
    df['macd_hist'] = df['macd_dif'] - df['macd_dea']

    # ATR
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    df['atr14'] = tr.rolling(14).mean()
    df['atr20'] = tr.rolling(20).mean()

    # Bollinger Bands
    df['boll_mid'] = df['close'].rolling(20).mean()
    std = df['close'].rolling(20).std()
    df['boll_upper'] = df['boll_mid'] + 2 * std
    df['boll_lower'] = df['boll_mid'] - 2 * std
    df['boll_width'] = (df['boll_upper'] - df['boll_lower']) / df['boll_mid']

    # KDJ
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100
    df['kdj_k'] = rsv.ewm(com=2).mean()
    df['kdj_d'] = df['kdj_k'].ewm(com=2).mean()
    df['kdj_j'] = 3 * df['kdj_k'] - 2 * df['kdj_d']

    # 量比
    df['volume_ratio'] = df['vol'] / df['vol_sma5']

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
