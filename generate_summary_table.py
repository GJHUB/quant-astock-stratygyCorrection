#!/usr/bin/env python3
"""
生成买卖点汇总表格
"""

import sys
import pandas as pd
from datetime import datetime, timedelta
from data_loader import load_multiple_stocks_as_dataframe
from indicators import calculate_global_indicators
from signals import generate_signals

# 最优参数
BEST_PARAMS = {
    'theta_buy': 10.0,
    'theta_sell': 10.0,
    'alpha_vol': 0.8
}

# 股票池
STOCK_POOL = [
    '300308.SZ', '300502.SZ', '603083.SH', '300548.SZ',
    '300570.SZ', '688498.SH', '002902.SZ', '300620.SZ',
    '300395.SZ', '002371.SZ', '688981.SH', '603501.SH',
    '600460.SH', '688099.SH', '300782.SZ', '688608.SH',
    '688258.SH', '688017.SH', '601689.SH', '603728.SH',
    '688256.SH', '688041.SH', '688047.SH', '300474.SZ',
    '601138.SH', '002837.SZ', '300499.SZ', '300730.SZ',
    '000977.SZ', '603019.SH'
]

STOCK_NAMES = {
    '300308.SZ': '中际旭创', '300502.SZ': '新易盛', '603083.SH': '剑桥科技',
    '300548.SZ': '博创科技', '300570.SZ': '太辰光', '688498.SH': '源杰科技',
    '002902.SZ': '铭普光磁', '300620.SZ': '光库科技', '300395.SZ': '菲利华',
    '002371.SZ': '北方华创', '688981.SH': '中芯国际', '603501.SH': '韦尔股份',
    '600460.SH': '士兰微', '688099.SH': '晶晨股份', '300782.SZ': '卓胜微',
    '688608.SH': '恒玄科技', '688258.SH': '优必选', '688017.SH': '绿的谐波',
    '601689.SH': '拓普集团', '603728.SH': '鸣志电器', '688256.SH': '寒武纪',
    '688041.SH': '海光信息', '688047.SH': '龙芯中科', '300474.SZ': '景嘉微',
    '601138.SH': '工业富联', '002837.SZ': '英维克', '300499.SZ': '高澜股份',
    '300730.SZ': '曙光数创', '000977.SZ': '浪潮信息', '603019.SH': '中科曙光'
}


def generate_summary_table():
    """生成买卖点汇总表格"""
    print("=" * 80)
    print("股票池买卖点汇总表格生成")
    print("=" * 80)
    
    # 计算日期范围（过去12个月）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    print(f"\n正在加载数据 ({start_str} - {end_str})...")
    
    # 加载数据
    df_all = load_multiple_stocks_as_dataframe(
        stock_list=STOCK_POOL,
        start_date=start_str,
        end_date=end_str
    )
    
    if len(df_all) == 0:
        print("错误：没有加载到任何数据")
        return
    
    print(f"成功加载 {len(df_all)} 条记录")
    
    # 计算指标和信号
    print("正在计算指标和信号...")
    df_prepared = calculate_global_indicators(df_all)
    df_prepared = generate_signals(
        df_prepared,
        theta_buy=BEST_PARAMS['theta_buy'],
        theta_sell=BEST_PARAMS['theta_sell'],
        alpha_vol=BEST_PARAMS['alpha_vol']
    )
    
    # 汇总结果
    results = []
    
    for ts_code in STOCK_POOL:
        df_stock = df_prepared[df_prepared['ts_code'] == ts_code].copy()
        
        if len(df_stock) == 0:
            continue
        
        stock_name = STOCK_NAMES.get(ts_code, ts_code)
        
        # 获取买卖点
        buy_signals = df_stock[df_stock['buy_signal']].copy()
        sell_signals = df_stock[df_stock['sell_signal']].copy()
        
        buy_count = len(buy_signals)
        sell_count = len(sell_signals)
        
        # 买点详情
        buy_details = []
        if buy_count > 0:
            for idx, row in buy_signals.iterrows():
                buy_details.append({
                    'date': row['trade_date'].strftime('%Y-%m-%d'),
                    'price': f"{row['close']:.2f}",
                    'bias': f"{row['BIAS_20']:.2f}%",
                    'volume_ratio': f"{row['volume'] / row['Vol_SMA_10']:.2f}"
                })
        
        # 卖点详情（只取前5个）
        sell_details = []
        if sell_count > 0:
            for idx, row in sell_signals.head(5).iterrows():
                sell_details.append({
                    'date': row['trade_date'].strftime('%Y-%m-%d'),
                    'price': f"{row['close']:.2f}",
                    'bias': f"{row['BIAS_20']:.2f}%"
                })
        
        results.append({
            'code': ts_code,
            'name': stock_name,
            'buy_count': buy_count,
            'sell_count': sell_count,
            'buy_details': buy_details,
            'sell_details': sell_details
        })
    
    # 生成汇总表格
    print("\n" + "=" * 80)
    print("买卖点汇总表格")
    print("=" * 80)
    
    # 创建DataFrame
    summary_data = []
    for r in results:
        buy_dates = ', '.join([d['date'] for d in r['buy_details']]) if r['buy_details'] else '-'
        buy_prices = ', '.join([d['price'] for d in r['buy_details']]) if r['buy_details'] else '-'
        
        summary_data.append({
            '股票代码': r['code'],
            '股票名称': r['name'],
            '买入次数': r['buy_count'],
            '卖出次数': r['sell_count'],
            '买入日期': buy_dates,
            '买入价格': buy_prices
        })
    
    df_summary = pd.DataFrame(summary_data)
    
    # 保存为CSV
    output_file = 'buy_sell_summary.csv'
    df_summary.to_csv(output_file, index=False, encoding='utf-8-sig')
    print(f"\n汇总表格已保存: {output_file}")
    
    # 打印表格
    print("\n" + df_summary.to_string(index=False))
    
    # 生成详细报告
    print("\n" + "=" * 80)
    print("买点详细信息")
    print("=" * 80)
    
    for r in results:
        if r['buy_count'] > 0:
            print(f"\n{r['name']} ({r['code']})")
            print(f"买入次数: {r['buy_count']}")
            for detail in r['buy_details']:
                print(f"  - {detail['date']}: 价格{detail['price']}元, "
                      f"乖离率{detail['bias']}, 量比{detail['volume_ratio']}")
    
    # 统计汇总
    print("\n" + "=" * 80)
    print("统计汇总")
    print("=" * 80)
    print(f"总股票数: {len(results)}")
    print(f"有买入信号的股票: {sum(1 for r in results if r['buy_count'] > 0)}")
    print(f"总买入信号数: {sum(r['buy_count'] for r in results)}")
    print(f"总卖出信号数: {sum(r['sell_count'] for r in results)}")
    
    return df_summary


if __name__ == '__main__':
    generate_summary_table()
