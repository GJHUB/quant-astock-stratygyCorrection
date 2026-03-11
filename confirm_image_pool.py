from stock_pool import build_stock_pool, IMAGE_STOCK_POOL
import psycopg2,pandas as pd
from config import DB_CONFIG
from datetime import datetime

pool = build_stock_pool(80)
codes = [x['ts_code'] for x in IMAGE_STOCK_POOL]
conn = psycopg2.connect(**DB_CONFIG)
df = pd.read_sql(
    "select ts_code,count(*) bars,max(trade_date) latest,avg(amount) avg_amount "
    "from kline_daily where ts_code=any(%s) and trade_date>='20180101' group by ts_code",
    conn, params=(codes,)
)
conn.close()

out='result_v3.2/stock_pool_from_image_confirm.md'
with open(out,'w',encoding='utf-8') as f:
    f.write('# 图片股票池确认\n\n')
    f.write('- 生成时间: %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    f.write('- 图片清单总数: %d\n' % len(IMAGE_STOCK_POOL))
    f.write('- 可用(>=200 bars): %d\n\n' % len(pool))
    f.write('| ts_code | 名称 | 赛道 | bars(2018+) | latest | avg_amount | 入池 |\n')
    f.write('|---|---|---|---:|---|---:|---|\n')
    for c in IMAGE_STOCK_POOL:
        r=df[df.ts_code==c['ts_code']]
        bars=int(r.bars.iloc[0]) if len(r) else 0
        latest=str(r.latest.iloc[0]) if len(r) else 'N/A'
        avg=float(r.avg_amount.iloc[0]) if len(r) else 0.0
        f.write('| %s | %s | %s | %d | %s | %.2f | %s |\n' % (
            c['ts_code'],c['name'],c['sector'],bars,latest,avg,'是' if c['ts_code'] in pool else '否'
        ))

print('POOL_SIZE',len(pool))
print('FILE',out)
print('TOP10',pool[:10])
