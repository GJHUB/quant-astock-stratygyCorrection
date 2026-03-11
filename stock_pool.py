#!/usr/bin/env python3
"""
股票池模块（按用户指定图片清单）
"""

import logging
from typing import List, Dict
import os
import re
import pandas as pd
import psycopg2
from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 按用户图片清单映射（v3.2 指定池）
TRAIN_STOCK_FILE = os.path.join(os.path.dirname(__file__), 'config_training_stocks.txt')

IMAGE_STOCK_POOL: List[Dict[str, str]] = [
    # 液冷
    {"ts_code": "002837.SZ", "name": "英维克", "sector": "液冷"},
    {"ts_code": "301018.SZ", "name": "申菱环境", "sector": "液冷"},
    {"ts_code": "301326.SZ", "name": "捷邦科技", "sector": "液冷"},
    {"ts_code": "300731.SZ", "name": "科创新源", "sector": "液冷"},
    {"ts_code": "002536.SZ", "name": "飞龙股份", "sector": "液冷"},
    {"ts_code": "300602.SZ", "name": "飞荣达", "sector": "液冷"},

    # 海外算力
    {"ts_code": "300308.SZ", "name": "中际旭创", "sector": "海外算力"},
    {"ts_code": "300502.SZ", "name": "新易盛", "sector": "海外算力"},
    {"ts_code": "002384.SZ", "name": "东山精密", "sector": "海外算力"},
    {"ts_code": "301217.SZ", "name": "铜冠铜箔", "sector": "海外算力"},
    {"ts_code": "001267.SZ", "name": "汇绿生态", "sector": "海外算力"},
    {"ts_code": "300394.SZ", "name": "天孚通信", "sector": "海外算力"},
    {"ts_code": "920045.BJ", "name": "蘅东光", "sector": "海外算力"},

    # 国产算力
    {"ts_code": "688629.SH", "name": "华丰科技", "sector": "国产算力"},
    {"ts_code": "002843.SZ", "name": "泰嘉股份", "sector": "国产算力"},
    {"ts_code": "002897.SZ", "name": "意华股份", "sector": "国产算力"},
    {"ts_code": "600589.SH", "name": "大位科技", "sector": "国产算力"},
    {"ts_code": "300442.SZ", "name": "润泽科技", "sector": "国产算力"},
    {"ts_code": "300846.SZ", "name": "首都在线", "sector": "国产算力"},
    {"ts_code": "688702.SH", "name": "盛科通信-U", "sector": "国产算力"},
    {"ts_code": "603881.SH", "name": "数据港", "sector": "国产算力"},
    {"ts_code": "000880.SZ", "name": "潍柴重机", "sector": "国产算力"},

    # 芯片
    {"ts_code": "688047.SH", "name": "龙芯中科", "sector": "芯片"},
    {"ts_code": "688110.SH", "name": "东芯股份", "sector": "芯片"},
    {"ts_code": "688343.SH", "name": "云天励飞-U", "sector": "芯片"},

    # 机器人
    {"ts_code": "002009.SZ", "name": "天奇股份", "sector": "机器人"},
    {"ts_code": "603331.SH", "name": "百达精工", "sector": "机器人"},
    {"ts_code": "603667.SH", "name": "五洲新春", "sector": "机器人"},
    {"ts_code": "000700.SZ", "name": "模塑科技", "sector": "机器人"},
    {"ts_code": "300718.SZ", "name": "长盛轴承", "sector": "机器人"},
]


def _validate_codes(codes: List[str], min_bars: int = 200) -> List[str]:
    conn = psycopg2.connect(**DB_CONFIG)
    q = """
        SELECT ts_code, COUNT(*) AS bars
        FROM kline_daily
        WHERE ts_code = ANY(%s)
          AND trade_date >= '20180101'
        GROUP BY ts_code
    """
    df = pd.read_sql(q, conn, params=(codes,))
    conn.close()
    bars_map = {r.ts_code: int(r.bars) for _, r in df.iterrows()}
    return [c for c in codes if bars_map.get(c, 0) >= min_bars]


def get_training_stock_pool() -> List[str]:
    """从 config_training_stocks.txt 加载调参训练集股票列表。"""
    if not os.path.exists(TRAIN_STOCK_FILE):
        logger.error(f"训练集文件不存在: {TRAIN_STOCK_FILE}")
        return []

    codes: List[str] = []
    p = re.compile(r'\b\d{6}\b')
    with open(TRAIN_STOCK_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            m = p.search(line)
            if not m:
                continue
            code6 = m.group(0)
            if code6.startswith(('600', '601', '603', '605', '688')):
                ts_code = f"{code6}.SH"
            elif code6.startswith(('000', '001', '002', '003', '300', '301')):
                ts_code = f"{code6}.SZ"
            else:
                ts_code = code6
            if ts_code not in codes:
                codes.append(ts_code)

    valid = _validate_codes(codes, min_bars=200)
    logger.info(f"训练集配置总数: {len(codes)}，可用(>=200 bars): {len(valid)}")
    return valid


def build_stock_pool(target_size: int = 80) -> List[str]:
    """
    按用户图片清单返回回测测试集股票池，并校验数据可用性。
    """
    conn = psycopg2.connect(**DB_CONFIG)
    codes = [x["ts_code"] for x in IMAGE_STOCK_POOL]

    q = """
        SELECT ts_code, COUNT(*) AS bars, MAX(trade_date) AS latest
        FROM kline_daily
        WHERE ts_code = ANY(%s)
          AND trade_date >= '20180101'
        GROUP BY ts_code
    """
    df = pd.read_sql(q, conn, params=(codes,))
    conn.close()

    bars_map = {r.ts_code: int(r.bars) for _, r in df.iterrows()}
    valid = [x for x in IMAGE_STOCK_POOL if x["ts_code"] in bars_map and bars_map[x["ts_code"]] >= 200]
    pool = [x["ts_code"] for x in valid]

    logger.info("=" * 80)
    logger.info("股票池构建完成（按用户图片清单）")
    logger.info("=" * 80)
    logger.info(f"图片清单总数: {len(IMAGE_STOCK_POOL)}")
    logger.info(f"可用股票数(>=200 bars): {len(pool)}")
    logger.info("=" * 80)

    for x in valid[:20]:
        logger.info(f"  {x['ts_code']} {x['name']}({x['sector']}) bars={bars_map.get(x['ts_code'], 0)}")

    return pool


if __name__ == '__main__':
    p = build_stock_pool()
    print(len(p), p)
