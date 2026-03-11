import psycopg2
from psycopg2.extras import execute_values
import pandas as pd
import numpy as np
from datetime import datetime

from config import DB_CONFIG
from stock_pool import get_training_stock_pool, build_stock_pool

START = '20180101'
END = datetime.now().strftime('%Y%m%d')


def apply_qfq(df: pd.DataFrame) -> pd.DataFrame:
    """前复权：price_qfq = price_raw * adj_factor / latest_adj_factor"""
    out = df.copy()
    if 'adj_factor' not in out.columns:
        return out
    out['adj_factor'] = pd.to_numeric(out['adj_factor'], errors='coerce')
    latest = out['adj_factor'].dropna()
    if latest.empty:
        return out
    latest_factor = float(latest.iloc[-1])
    if latest_factor == 0:
        return out
    ratio = out['adj_factor'] / latest_factor
    for c in ['open','high','low','close']:
        out[c] = pd.to_numeric(out[c], errors='coerce') * ratio
    return out


def rsi(series, period):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def calc(df):
    out = df.copy()
    out['sma5'] = out['close'].rolling(5).mean()
    out['sma10'] = out['close'].rolling(10).mean()
    out['sma20'] = out['close'].rolling(20).mean()
    out['sma60'] = out['close'].rolling(60).mean()
    out['sma200'] = out['close'].rolling(200).mean()

    out['vol_sma5'] = out['vol'].rolling(5).mean()
    out['vol_sma10'] = out['vol'].rolling(10).mean()
    out['vol_sma20'] = out['vol'].rolling(20).mean()

    out['bias5'] = (out['close'] - out['sma5']) / out['sma5'] * 100
    out['bias10'] = (out['close'] - out['sma10']) / out['sma10'] * 100
    out['bias20'] = (out['close'] - out['sma20']) / out['sma20'] * 100
    out['bias60'] = (out['close'] - out['sma60']) / out['sma60'] * 100

    out['rsi6'] = rsi(out['close'], 6)
    out['rsi12'] = rsi(out['close'], 12)
    out['rsi14'] = rsi(out['close'], 14)
    out['rsi24'] = rsi(out['close'], 24)

    ema12 = out['close'].ewm(span=12, adjust=False).mean()
    ema26 = out['close'].ewm(span=26, adjust=False).mean()
    out['macd_dif'] = ema12 - ema26
    out['macd_dea'] = out['macd_dif'].ewm(span=9, adjust=False).mean()
    out['macd_hist'] = 2 * (out['macd_dif'] - out['macd_dea'])

    out['boll_mid'] = out['close'].rolling(20).mean()
    std20 = out['close'].rolling(20).std()
    out['boll_upper'] = out['boll_mid'] + 2 * std20
    out['boll_lower'] = out['boll_mid'] - 2 * std20
    out['boll_width'] = (out['boll_upper'] - out['boll_lower']) / out['boll_mid']

    high_low = out['high'] - out['low']
    high_close = (out['high'] - out['close'].shift()).abs()
    low_close = (out['low'] - out['close'].shift()).abs()
    tr = pd.concat([high_low, high_close, low_close], axis=1).max(axis=1)
    out['atr14'] = tr.rolling(14).mean()
    out['atr20'] = tr.rolling(20).mean()

    low_min = out['low'].rolling(9).min()
    high_max = out['high'].rolling(9).max()
    rsv = (out['close'] - low_min) / (high_max - low_min).replace(0, np.nan) * 100
    out['kdj_k'] = rsv.ewm(com=2, adjust=False).mean()
    out['kdj_d'] = out['kdj_k'].ewm(com=2, adjust=False).mean()
    out['kdj_j'] = 3 * out['kdj_k'] - 2 * out['kdj_d']

    out['volume_ratio'] = out['vol'] / out['vol_sma5']
    return out


def nv(x):
    return None if pd.isna(x) else float(x)


def main():
    train = get_training_stock_pool()
    test = build_stock_pool()
    codes = sorted(set(train + test))
    print(f'TRAIN={len(train)} TEST={len(test)} UNION={len(codes)}')

    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()

    sel_sql = """
        SELECT k.trade_date, k.open, k.high, k.low, k.close, k.vol, k.amount, a.adj_factor
        FROM kline_daily k
        LEFT JOIN adj_factor a ON a.ts_code = k.ts_code AND a.trade_date = k.trade_date
        WHERE k.ts_code=%s AND k.trade_date >= %s AND k.trade_date <= %s
        ORDER BY k.trade_date
    """

    upsert_sql = """
        INSERT INTO technical_indicators (
            ts_code, trade_date, sma5, sma10, sma20, sma60, sma200,
            vol_sma5, vol_sma10, vol_sma20,
            bias5, bias10, bias20, bias60,
            rsi6, rsi12, rsi14, rsi24,
            macd_dif, macd_dea, macd_hist,
            boll_upper, boll_mid, boll_lower, boll_width,
            atr14, atr20,
            kdj_k, kdj_d, kdj_j,
            volume_ratio, updated_at
        ) VALUES %s
        ON CONFLICT (ts_code, trade_date)
        DO UPDATE SET
            sma5=EXCLUDED.sma5, sma10=EXCLUDED.sma10, sma20=EXCLUDED.sma20, sma60=EXCLUDED.sma60, sma200=EXCLUDED.sma200,
            vol_sma5=EXCLUDED.vol_sma5, vol_sma10=EXCLUDED.vol_sma10, vol_sma20=EXCLUDED.vol_sma20,
            bias5=EXCLUDED.bias5, bias10=EXCLUDED.bias10, bias20=EXCLUDED.bias20, bias60=EXCLUDED.bias60,
            rsi6=EXCLUDED.rsi6, rsi12=EXCLUDED.rsi12, rsi14=EXCLUDED.rsi14, rsi24=EXCLUDED.rsi24,
            macd_dif=EXCLUDED.macd_dif, macd_dea=EXCLUDED.macd_dea, macd_hist=EXCLUDED.macd_hist,
            boll_upper=EXCLUDED.boll_upper, boll_mid=EXCLUDED.boll_mid, boll_lower=EXCLUDED.boll_lower, boll_width=EXCLUDED.boll_width,
            atr14=EXCLUDED.atr14, atr20=EXCLUDED.atr20,
            kdj_k=EXCLUDED.kdj_k, kdj_d=EXCLUDED.kdj_d, kdj_j=EXCLUDED.kdj_j,
            volume_ratio=EXCLUDED.volume_ratio,
            updated_at=EXCLUDED.updated_at
    """

    total_rows = 0
    for i, code in enumerate(codes, 1):
        kdf = pd.read_sql(sel_sql, conn, params=(code, START, END))
        if kdf.empty:
            continue
        kdf['trade_date'] = kdf['trade_date'].astype(str)
        kdf = apply_qfq(kdf)
        kdf = calc(kdf)
        now = datetime.now()
        rows = []
        for _, r in kdf.iterrows():
            rows.append((
                code, r['trade_date'],
                nv(r['sma5']), nv(r['sma10']), nv(r['sma20']), nv(r['sma60']), nv(r['sma200']),
                nv(r['vol_sma5']), nv(r['vol_sma10']), nv(r['vol_sma20']),
                nv(r['bias5']), nv(r['bias10']), nv(r['bias20']), nv(r['bias60']),
                nv(r['rsi6']), nv(r['rsi12']), nv(r['rsi14']), nv(r['rsi24']),
                nv(r['macd_dif']), nv(r['macd_dea']), nv(r['macd_hist']),
                nv(r['boll_upper']), nv(r['boll_mid']), nv(r['boll_lower']), nv(r['boll_width']),
                nv(r['atr14']), nv(r['atr20']),
                nv(r['kdj_k']), nv(r['kdj_d']), nv(r['kdj_j']),
                nv(r['volume_ratio']), now
            ))
        execute_values(cur, upsert_sql, rows, page_size=1000)
        total_rows += len(rows)
        if i % 10 == 0:
            conn.commit()
            print(f'[{i}/{len(codes)}] upserted rows={total_rows}')

    conn.commit()

    # completeness check
    q = """
    WITH sel AS (
      SELECT unnest(%s::varchar[]) AS ts_code
    ), k AS (
      SELECT ts_code, count(*) k_cnt FROM kline_daily WHERE ts_code IN (SELECT ts_code FROM sel) AND trade_date>=%s AND trade_date<=%s GROUP BY ts_code
    ), t AS (
      SELECT ts_code, count(*) t_cnt FROM technical_indicators WHERE ts_code IN (SELECT ts_code FROM sel) AND trade_date>=%s AND trade_date<=%s GROUP BY ts_code
    )
    SELECT coalesce(sum(k.k_cnt),0), coalesce(sum(t.t_cnt),0) FROM k LEFT JOIN t USING(ts_code)
    """
    cur.execute(q, (codes, START, END, START, END))
    kcnt, tcnt = cur.fetchone()
    print(f'KLINE_ROWS={kcnt} TECH_ROWS={tcnt}')

    cur.close()
    conn.close()


if __name__ == '__main__':
    main()
