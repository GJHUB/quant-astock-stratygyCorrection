from stock_pool import build_stock_pool
import psycopg2, pandas as pd
from config import DB_CONFIG
from datetime import datetime

pool = build_stock_pool(80)
conn = psycopg2.connect(**DB_CONFIG)
q = """
select sp.ts_code, coalesce(sp.name,sp.ts_code) as name, coalesce(sp.sector,'') as sector,
       count(k.*) as data_count, avg(k.amount) as avg_amount, max(k.trade_date) as latest_date
from stock_pool sp
join kline_daily k on sp.ts_code=k.ts_code
where sp.status='active' and sp.ts_code = any(%s)
group by sp.ts_code,sp.name,sp.sector
order by avg_amount desc
"""
df = pd.read_sql(q, conn, params=(pool,))
conn.close()

out='result_v3.2/stock_pool_import_summary.md'
with open(out,'w',encoding='utf-8') as f:
    f.write('# 股票池导入确认（v3.2）\n\n')
    f.write('- 生成时间: %s\n' % datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    f.write('- 股票池数量: %d\n' % len(pool))
    f.write('- 最新交易日: %s\n\n' % (df.latest_date.max() if not df.empty else 'N/A'))
    f.write('| ts_code | name | sector | data_count | avg_amount | latest_date |\n')
    f.write('|---|---|---|---:|---:|---|\n')
    for _,r in df.head(80).iterrows():
        f.write('| %s | %s | %s | %d | %.2f | %s |\n' % (r.ts_code, r.name, r.sector, int(r.data_count), r.avg_amount, r.latest_date))

print('POOL_SIZE',len(pool))
print('SUMMARY',out)
print(df.head(20).to_string(index=False))
