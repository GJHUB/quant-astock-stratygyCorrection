"""
数据加载模块：从PostgreSQL加载数据、筛选股票池
优化版：支持全局指标预计算
"""

import pandas as pd
import psycopg2
from psycopg2.extras import RealDictCursor
from config import DB_CONFIG, STOCK_POOL_CONFIG, DATA_CONFIG


def get_db_connection():
    """建立数据库连接"""
    return psycopg2.connect(**DB_CONFIG)


def load_stock_list():
    """从数据库加载所有股票列表"""
    conn = get_db_connection()
    query = """
        SELECT DISTINCT ts_code
        FROM kline_daily
        WHERE trade_date >= %s AND trade_date <= %s
        ORDER BY ts_code
    """
    df = pd.read_sql(query, conn, params=(DATA_CONFIG['start_date'], DATA_CONFIG['end_date']))
    conn.close()
    return df['ts_code'].tolist()


def load_stock_data(ts_code, start_date=None, end_date=None):
    """
    加载单只股票的日线数据

    Parameters:
    -----------
    ts_code : str
        股票代码
    start_date : str, optional
        起始日期 YYYYMMDD
    end_date : str, optional
        结束日期 YYYYMMDD

    Returns:
    --------
    pd.DataFrame
        包含 trade_date, open, high, low, close, vol, amount
    """
    conn = get_db_connection()

    start = start_date or DATA_CONFIG['start_date']
    end = end_date or DATA_CONFIG['end_date']

    query = """
        SELECT trade_date, open, high, low, close, vol as volume, amount
        FROM kline_daily
        WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s
        ORDER BY trade_date
    """

    df = pd.read_sql(query, conn, params=(ts_code, start, end))
    conn.close()

    # 转换日期格式
    df['trade_date'] = pd.to_datetime(df['trade_date'], format='%Y%m%d')
    df = df.set_index('trade_date')
    
    # 添加股票代码列（用于全局指标计算）
    df['ts_code'] = ts_code

    return df


def load_multiple_stocks(stock_list, start_date=None, end_date=None):
    """
    批量加载多只股票数据

    Returns:
    --------
    dict
        {ts_code: DataFrame}
    """
    data_dict = {}
    for i, ts_code in enumerate(stock_list):
        if i % 20 == 0:
            print(f"加载数据进度: {i}/{len(stock_list)}")
        try:
            df = load_stock_data(ts_code, start_date, end_date)
            if len(df) > 100:  # 确保有足够的数据
                data_dict[ts_code] = df
        except Exception as e:
            print(f"加载 {ts_code} 失败: {e}")

    print(f"成功加载 {len(data_dict)} 只股票数据")
    return data_dict


def load_multiple_stocks_as_dataframe(stock_list, start_date=None, end_date=None):
    """
    批量加载多只股票数据，返回单个DataFrame（用于全局指标计算）
    
    Returns:
    --------
    pd.DataFrame
        包含所有股票的数据，带有 ts_code 列
    """
    all_data = []
    for i, ts_code in enumerate(stock_list):
        if i % 20 == 0:
            print(f"加载数据进度: {i}/{len(stock_list)}")
        try:
            df = load_stock_data(ts_code, start_date, end_date)
            if len(df) > 100:
                df = df.reset_index()
                df['ts_code'] = ts_code
                all_data.append(df)
        except Exception as e:
            print(f"加载 {ts_code} 失败: {e}")
    
    if len(all_data) == 0:
        return pd.DataFrame()
    
    # 合并所有数据
    df_all = pd.concat(all_data, ignore_index=True)
    df_all = df_all.sort_values(['ts_code', 'trade_date'])
    
    print(f"成功加载 {len(all_data)} 只股票数据，共 {len(df_all)} 条记录")
    return df_all
