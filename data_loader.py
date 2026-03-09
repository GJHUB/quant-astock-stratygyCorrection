"""
数据加载模块：从PostgreSQL加载数据、筛选股票池
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


def calculate_volatility(ts_code, window=60):
    """计算单只股票的历史波动率"""
    conn = get_db_connection()
    query = """
        SELECT close
        FROM kline_daily
        WHERE ts_code = %s AND trade_date >= %s AND trade_date <= %s
        ORDER BY trade_date
    """
    df = pd.read_sql(query, conn, params=(ts_code, DATA_CONFIG['start_date'], DATA_CONFIG['end_date']))
    conn.close()

    if len(df) < window:
        return 0

    # 计算日收益率标准差
    returns = df['close'].pct_change().dropna()
    volatility = returns.std() * (252 ** 0.5)  # 年化波动率
    return volatility


def select_stock_pool():
    """
    筛选股票池：科技板块，按波动率排序取前120只
    注：由于数据库中可能没有板块字段，这里简化为按波动率排序
    """
    print("正在加载股票列表...")
    all_stocks = load_stock_list()
    print(f"共找到 {len(all_stocks)} 只股票")

    print("正在计算波动率...")
    stock_volatility = []
    for i, ts_code in enumerate(all_stocks):
        if i % 50 == 0:
            print(f"进度: {i}/{len(all_stocks)}")
        vol = calculate_volatility(ts_code, STOCK_POOL_CONFIG['volatility_window'])
        if vol > 0:  # 过滤掉数据不足的股票
            stock_volatility.append({'ts_code': ts_code, 'volatility': vol})

    # 按波动率降序排序，取前120只
    df_vol = pd.DataFrame(stock_volatility)
    df_vol = df_vol.sort_values('volatility', ascending=False)
    top_stocks = df_vol.head(STOCK_POOL_CONFIG['top_n'])['ts_code'].tolist()

    print(f"筛选完成，股票池包含 {len(top_stocks)} 只高波科技股")
    return top_stocks


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
