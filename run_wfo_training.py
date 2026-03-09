#!/usr/bin/env python3
"""
QuantV2 策略 WFO 调参脚本（训练集）
使用30只核心股票进行参数优化
"""

import sys
import json
from datetime import datetime
from data_loader import load_multiple_stocks
from wfo_optimizer import run_wfo

# 训练集：30只核心股票
TRAINING_STOCKS = [
    # CPO/光模块子板块（8只）
    '300308.SZ',  # 中际旭创
    '300502.SZ',  # 新易盛
    '603083.SH',  # 剑桥科技
    '300548.SZ',  # 博创科技
    '300570.SZ',  # 太辰光
    '688498.SH',  # 源杰科技
    '002902.SZ',  # 铭普光磁
    '300620.SZ',  # 光库科技
    
    # 半导体/芯片子板块（8只）
    '300395.SZ',  # 菲利华
    '002371.SZ',  # 北方华创
    '688981.SH',  # 中芯国际
    '603501.SH',  # 韦尔股份
    '600460.SH',  # 士兰微
    '688099.SH',  # 晶晨股份
    '300782.SZ',  # 卓胜微
    '688608.SH',  # 恒玄科技
    
    # 人形机器人/国产算力子板块（8只）
    '688258.SH',  # 优必选
    '688017.SH',  # 绿的谐波
    '601689.SH',  # 拓普集团
    '603728.SH',  # 鸣志电器
    '688256.SH',  # 寒武纪
    '688041.SH',  # 海光信息
    '688047.SH',  # 龙芯中科
    '300474.SZ',  # 景嘉微
    
    # 液冷/海外算力子板块（6只）
    '601138.SH',  # 工业富联
    '002837.SZ',  # 英维克
    '300499.SZ',  # 高澜股份
    '300730.SZ',  # 曙光数创
    '000977.SZ',  # 浪潮信息
    '603019.SH',  # 中科曙光
]

# WFO时间窗口配置（按训练集方案）
WFO_WINDOWS = [
    # 窗口1
    {
        'train_start': '20230101',
        'train_end': '20231231',
        'test_start': '20240101',
        'test_end': '20240331'
    },
    # 窗口2
    {
        'train_start': '20230401',
        'train_end': '20240331',
        'test_start': '20240401',
        'test_end': '20240630'
    },
    # 窗口3
    {
        'train_start': '20230701',
        'train_end': '20240630',
        'test_start': '20240701',
        'test_end': '20240930'
    },
    # 窗口4
    {
        'train_start': '20231001',
        'train_end': '20240930',
        'test_start': '20241001',
        'test_end': '20250331'
    },
    # 窗口5
    {
        'train_start': '20240101',
        'train_end': '20250331',
        'test_start': '20250401',
        'test_end': '20260228'
    },
]


def main():
    print("=" * 80)
    print("QuantV2 策略 WFO 调参（训练集）")
    print("=" * 80)
    print(f"训练股票数量: {len(TRAINING_STOCKS)}")
    print(f"时间窗口数量: {len(WFO_WINDOWS)}")
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    # 加载训练集数据
    print("\n正在加载训练集数据...")
    print(f"目标股票数量: {len(TRAINING_STOCKS)}")
    print(f"时间范围: 20230101 - 20260228")
    
    data_dict = load_multiple_stocks(
        stock_list=TRAINING_STOCKS,
        start_date='20230101',
        end_date='20260228'
    )
    
    print(f"\n成功加载 {len(data_dict)} 只股票数据")
    print("数据加载完成，准备开始WFO优化...")
    import sys
    sys.stdout.flush()
    
    if len(data_dict) == 0:
        print("错误：没有加载到任何数据")
        sys.exit(1)
    
    # 运行WFO优化
    print("\n开始 Walk-Forward Optimization...")
    sys.stdout.flush()
    
    try:
        wfo_results = run_wfo(
            data_dict=data_dict,
            start_date='20230101',
            end_date='20260228'
        )
        print("\nWFO优化完成！")
        sys.stdout.flush()
    except Exception as e:
        print(f"\n错误：WFO优化失败")
        print(f"错误信息: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    # 保存结果
    output_file = f"wfo_training_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(wfo_results, f, indent=2, ensure_ascii=False)
    
    print(f"\n结果已保存到: {output_file}")
    
    # 打印汇总
    summary = wfo_results.get('summary', {})
    print("\n" + "=" * 80)
    print("WFO 汇总结果")
    print("=" * 80)
    print(f"总窗口数: {summary.get('total_windows', 0)}")
    print(f"平均测试集 Calmar Ratio: {summary.get('avg_test_calmar', 0):.4f}")
    print(f"平均测试集年化收益: {summary.get('avg_test_return', 0):.2f}%")
    print(f"平均测试集最大回撤: {summary.get('avg_test_drawdown', 0):.2f}%")
    
    best_window = summary.get('best_window', {})
    if best_window:
        print(f"\n最佳窗口: 窗口 {best_window.get('window', 0)}")
        print(f"  测试期间: {best_window.get('test_period', '')}")
        print(f"  最佳参数: {best_window.get('best_params', {})}")
        print(f"  Calmar Ratio: {best_window.get('test_metrics', {}).get('calmar_ratio', 0):.4f}")
    
    print("\n" + "=" * 80)
    print(f"完成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)


if __name__ == '__main__':
    main()
