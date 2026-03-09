#!/usr/bin/env python3
"""
股票池买卖点分析脚本
使用WFO最优参数在股票池中寻找过去12个月的买卖点
并生成K线图标注买卖点
"""

import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime, timedelta
from data_loader import load_multiple_stocks_as_dataframe
from indicators import calculate_global_indicators
from signals import generate_signals

# 设置中文字体（修复乱码问题）
import matplotlib
matplotlib.use('Agg')  # 使用非交互式后端
plt.rcParams['font.family'] = ['sans-serif']
plt.rcParams['font.sans-serif'] = ['Arial Unicode MS', 'SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

# 最优参数（来自WFO窗口5）
BEST_PARAMS = {
    'theta_buy': 10.0,
    'theta_sell': 10.0,
    'alpha_vol': 0.8
}

# 股票池（30只训练集股票）
STOCK_POOL = [
    # CPO/光模块
    '300308.SZ', '300502.SZ', '603083.SH', '300548.SZ',
    '300570.SZ', '688498.SH', '002902.SZ', '300620.SZ',
    # 半导体/芯片
    '300395.SZ', '002371.SZ', '688981.SH', '603501.SH',
    '600460.SH', '688099.SH', '300782.SZ', '688608.SH',
    # 人形机器人/国产算力
    '688258.SH', '688017.SH', '601689.SH', '603728.SH',
    '688256.SH', '688041.SH', '688047.SH', '300474.SZ',
    # 液冷/海外算力
    '601138.SH', '002837.SZ', '300499.SZ', '300730.SZ',
    '000977.SZ', '603019.SH'
]

# 股票名称映射
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


def plot_candlestick_with_signals(df, ts_code, output_dir='./charts'):
    """
    绘制K线图并标注买卖点
    """
    import os
    os.makedirs(output_dir, exist_ok=True)
    
    # 只绘制有买卖信号的股票
    if df['buy_signal'].sum() == 0 and df['sell_signal'].sum() == 0:
        return None
    
    stock_name = STOCK_NAMES.get(ts_code, ts_code)
    
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(16, 10), 
                                     gridspec_kw={'height_ratios': [3, 1]})
    
    # 准备数据
    df_plot = df.copy()
    df_plot['date_num'] = mdates.date2num(df_plot['trade_date'])
    
    # 绘制K线
    for idx, row in df_plot.iterrows():
        color = 'red' if row['close'] >= row['open'] else 'green'
        # 实体
        ax1.plot([row['date_num'], row['date_num']], 
                [row['open'], row['close']], 
                color=color, linewidth=6, solid_capstyle='round')
        # 上下影线
        ax1.plot([row['date_num'], row['date_num']], 
                [row['low'], row['high']], 
                color=color, linewidth=1)
    
    # 绘制均线
    ax1.plot(df_plot['date_num'], df_plot['SMA_20'], 
            label='MA20', color='blue', linewidth=1.5, alpha=0.7)
    ax1.plot(df_plot['date_num'], df_plot['SMA_60'], 
            label='MA60', color='orange', linewidth=1.5, alpha=0.7)
    
    # 标注买点
    buy_points = df_plot[df_plot['buy_signal']]
    if len(buy_points) > 0:
        ax1.scatter(buy_points['date_num'], buy_points['low'] * 0.98, 
                   marker='^', color='red', s=200, label='买入点', zorder=5)
        for idx, row in buy_points.iterrows():
            ax1.annotate(f"买\n{row['trade_date'].strftime('%m-%d')}", 
                        xy=(row['date_num'], row['low'] * 0.98),
                        xytext=(0, -30), textcoords='offset points',
                        ha='center', fontsize=9, color='red',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.7))
    
    # 标注卖点
    sell_points = df_plot[df_plot['sell_signal']]
    if len(sell_points) > 0:
        ax1.scatter(sell_points['date_num'], sell_points['high'] * 1.02, 
                   marker='v', color='green', s=200, label='卖出点', zorder=5)
        for idx, row in sell_points.iterrows():
            ax1.annotate(f"卖\n{row['trade_date'].strftime('%m-%d')}", 
                        xy=(row['date_num'], row['high'] * 1.02),
                        xytext=(0, 30), textcoords='offset points',
                        ha='center', fontsize=9, color='green',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='lightblue', alpha=0.7))
    
    # 设置K线图
    ax1.set_title(f'{stock_name} ({ts_code}) - 买卖点分析 (过去12个月)', 
                 fontsize=14, fontweight='bold')
    ax1.set_ylabel('价格 (元)', fontsize=12)
    ax1.legend(loc='upper left', fontsize=10)
    ax1.grid(True, alpha=0.3)
    ax1.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax1.xaxis.set_major_locator(mdates.MonthLocator())
    
    # 绘制成交量
    colors = ['red' if row['close'] >= row['open'] else 'green' 
             for idx, row in df_plot.iterrows()]
    ax2.bar(df_plot['date_num'], df_plot['volume'], 
           color=colors, alpha=0.6, width=0.6)
    ax2.plot(df_plot['date_num'], df_plot['Vol_SMA_10'], 
            label='10日均量', color='blue', linewidth=1.5)
    
    ax2.set_xlabel('日期', fontsize=12)
    ax2.set_ylabel('成交量', fontsize=12)
    ax2.legend(loc='upper left', fontsize=10)
    ax2.grid(True, alpha=0.3)
    ax2.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
    ax2.xaxis.set_major_locator(mdates.MonthLocator())
    
    plt.tight_layout()
    
    # 保存图片
    output_file = f"{output_dir}/{ts_code}_{stock_name}.png"
    plt.savefig(output_file, dpi=100, bbox_inches='tight')
    plt.close()
    
    return output_file


def analyze_stock_pool():
    """
    分析股票池中的买卖点
    """
    print("=" * 80)
    print("股票池买卖点分析")
    print("=" * 80)
    print(f"分析期间: 过去12个月")
    print(f"股票数量: {len(STOCK_POOL)}")
    print(f"最优参数: theta_buy={BEST_PARAMS['theta_buy']}, "
          f"theta_sell={BEST_PARAMS['theta_sell']}, "
          f"alpha_vol={BEST_PARAMS['alpha_vol']}")
    print("=" * 80)
    
    # 计算日期范围（过去12个月）
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365)
    
    start_str = start_date.strftime('%Y%m%d')
    end_str = end_date.strftime('%Y%m%d')
    
    print(f"\n正在加载股票池数据 ({start_str} - {end_str})...")
    
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
    
    # 全局指标预计算
    print("\n正在计算技术指标...")
    df_prepared = calculate_global_indicators(df_all)
    
    # 生成买卖信号
    print("正在生成买卖信号...")
    df_prepared = generate_signals(
        df_prepared,
        theta_buy=BEST_PARAMS['theta_buy'],
        theta_sell=BEST_PARAMS['theta_sell'],
        alpha_vol=BEST_PARAMS['alpha_vol']
    )
    
    # 统计结果
    results = []
    
    print("\n" + "=" * 80)
    print("买卖点统计")
    print("=" * 80)
    
    for ts_code in STOCK_POOL:
        df_stock = df_prepared[df_prepared['ts_code'] == ts_code].copy()
        
        if len(df_stock) == 0:
            continue
        
        buy_count = df_stock['buy_signal'].sum()
        sell_count = df_stock['sell_signal'].sum()
        
        if buy_count > 0 or sell_count > 0:
            stock_name = STOCK_NAMES.get(ts_code, ts_code)
            
            # 获取买卖点日期
            buy_dates = df_stock[df_stock['buy_signal']]['trade_date'].tolist()
            sell_dates = df_stock[df_stock['sell_signal']]['trade_date'].tolist()
            
            results.append({
                'ts_code': ts_code,
                'name': stock_name,
                'buy_count': int(buy_count),
                'sell_count': int(sell_count),
                'buy_dates': buy_dates,
                'sell_dates': sell_dates
            })
            
            print(f"\n{stock_name} ({ts_code})")
            print(f"  买入信号: {buy_count}次")
            if buy_count > 0:
                for date in buy_dates:
                    print(f"    - {date.strftime('%Y-%m-%d')}")
            print(f"  卖出信号: {sell_count}次")
            if sell_count > 0:
                for date in sell_dates:
                    print(f"    - {date.strftime('%Y-%m-%d')}")
            
            # 绘制K线图
            print(f"  正在生成K线图...")
            chart_file = plot_candlestick_with_signals(df_stock, ts_code)
            if chart_file:
                print(f"  ✓ 图表已保存: {chart_file}")
    
    # 汇总统计
    print("\n" + "=" * 80)
    print("汇总统计")
    print("=" * 80)
    print(f"有信号的股票数: {len(results)}/{len(STOCK_POOL)}")
    print(f"总买入信号数: {sum(r['buy_count'] for r in results)}")
    print(f"总卖出信号数: {sum(r['sell_count'] for r in results)}")
    print(f"平均每只股票买入次数: {sum(r['buy_count'] for r in results) / len(results):.1f}" if results else "0")
    
    print("\n图表已保存到: ./charts/ 目录")
    print("=" * 80)
    
    return results


if __name__ == '__main__':
    analyze_stock_pool()
