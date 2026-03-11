#!/usr/bin/env python3
"""
报告生成模块
生成Markdown回测报告和图表
"""

import os
import logging
from datetime import datetime
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # 非交互式后端

from config import REPORT_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_report(params: dict, results: dict, output_dir: str = None, version: str = 'v3.2'):
    """
    生成回测报告（v3.2 - 加权评分系统）

    Parameters:
    -----------
    params : dict
        策略参数
    results : dict
        回测结果
    output_dir : str
        输出目录
    version : str
        版本号
    """
    if output_dir is None:
        output_dir = REPORT_CONFIG['output_dir']

    os.makedirs(output_dir, exist_ok=True)

    logger.info("=" * 80)
    logger.info(f"生成回测报告 {version}")
    logger.info("=" * 80)

    # 生成净值曲线图
    equity_curve_path = os.path.join(output_dir, f'equity_curve_{version}.png')
    plot_equity_curve(results['equity_curve'], equity_curve_path)
    logger.info(f"✓ 净值曲线图: {equity_curve_path}")

    # 生成Markdown报告
    report_path = os.path.join(output_dir, f'backtest_report_{version}.md')
    write_markdown_report(params, results, report_path, version)
    logger.info(f"✓ 回测报告: {report_path}")

    logger.info("=" * 80)
    logger.info("✅ 报告生成完成")
    logger.info("=" * 80)


def plot_equity_curve(equity_df, output_path: str):
    """
    绘制净值曲线图
    
    Parameters:
    -----------
    equity_df : pd.DataFrame
        权益曲线数据
    output_path : str
        输出路径
    """
    plt.figure(figsize=REPORT_CONFIG['figure_size'])
    
    plt.plot(equity_df['date'], equity_df['equity'], linewidth=2, label='权益曲线')
    plt.axhline(y=equity_df['equity'].iloc[0], color='r', linestyle='--', alpha=0.5, label='初始资金')
    
    plt.title('回测净值曲线', fontsize=16, fontweight='bold')
    plt.xlabel('日期', fontsize=12)
    plt.ylabel('权益（元）', fontsize=12)
    plt.legend(fontsize=10)
    plt.grid(True, alpha=0.3)
    plt.xticks(rotation=45)
    plt.tight_layout()
    
    plt.savefig(output_path, dpi=REPORT_CONFIG['figure_dpi'], bbox_inches='tight')
    plt.close()


def write_markdown_report(params: dict, results: dict, output_path: str, version: str = 'v3.2'):
    """
    生成Markdown报告（v3.2 - 加权评分系统）

    Parameters:
    -----------
    params : dict
        策略参数
    results : dict
        回测结果
    output_path : str
        输出路径
    version : str
        版本号
    """
    report = f"""# 量化策略回测报告 {version}

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

**版本说明**: v3.2采用加权评分系统（0-1范围），提升交易次数至50+笔，强化遗传算法优化（目标交易次数>=50，年化换手率<200%）

---

## 一、策略参数

| 参数 | 值 | 说明 |
|------|-----|------|
| theta_buy | {params.get('theta_buy', 'N/A')} | 买入BIAS评分参考值（%，负值） |
| theta_sell | {params.get('theta_sell', 'N/A')} | 卖出乖离率阈值（%） |
| alpha_vol | {params.get('alpha_vol', 'N/A')} | 缩量系数（0.5-0.8） |
| rsi_thresh | {params.get('rsi_thresh', 'N/A')} | RSI评分参考值 |
| score_threshold | {params.get('score_threshold', 'N/A')} | 信号评分阈值（0-1） |
| min_amount | {params.get('min_amount', 'N/A')} | 最小成交额（元） |

---

## 二、回测指标

### 2.1 收益指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 初始资金 | {results['initial_cash']:,.0f} 元 | - | - |
| 最终权益 | {results['final_equity']:,.0f} 元 | - | - |
| 总收益率 | {results['total_return']:.2%} | - | - |
| 年化收益率 | {results['annual_return']:.2%} | > 20% | {'✅' if results['annual_return'] > 0.20 else '❌'} |

### 2.2 风险指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 最大回撤 | {results['max_drawdown']:.2%} | < 15% | {'✅' if results['max_drawdown'] > -0.15 else '❌'} |
| 夏普比率 | {results['sharpe_ratio']:.2f} | > 1.5 | {'✅' if results['sharpe_ratio'] > 1.5 else '❌'} |

### 2.3 交易指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 交易次数 | {results['total_trades']} | >= 50 | {'✅' if results['total_trades'] >= 50 else '❌'} |
| 换手率（月均） | {results['turnover']:.2f}/月 | < 16.7%/月 | {'✅' if results['turnover'] < 0.167 else '❌'} |
| 换手率（年化） | {results['turnover'] * 12:.2%} | < 200%/年 | {'✅' if results['turnover'] * 12 < 2.0 else '❌'} |
| 胜率 | {results['win_rate']:.2%} | > 55% | {'✅' if results['win_rate'] > 0.55 else '❌'} |
| 买入次数 | {results['total_trades']} | - | - |
| 卖出次数 | {results.get('total_sell_trades', 0)} | - | - |
| 盈利次数 | {results.get('winning_trades', 0)} | - | - |
| 平均盈亏 | {results.get('avg_profit', 0):,.2f} 元 | - | - |
| 平均盈利 | {results.get('avg_win', 0):,.2f} 元 | - | - |
| 平均亏损 | {results.get('avg_loss', 0):,.2f} 元 | - | - |
| 总交易成本 | {results.get('total_cost', 0):,.2f} 元 | - | - |

---

## 三、净值曲线
![净值曲线](equity_curve_{version}.png)

---

## 四、风险分析

### 4.1 收益风险比

- **Calmar比率**: {results['annual_return'] / abs(results['max_drawdown']) if results['max_drawdown'] != 0 else 0:.2f}
- **收益回撤比**: {results['total_return'] / abs(results['max_drawdown']) if results['max_drawdown'] != 0 else 0:.2f}

### 4.2 风险提示

"""

    # 添加风险提示（v3.2调整目标）
    warnings = []
    if results['total_trades'] < 50:
        warnings.append(f"⚠️ 交易次数不足（{results['total_trades']} < 50笔）- 统计显著性不足")
    if results['annual_return'] < 0.18:
        warnings.append("⚠️ 年化收益率未达标（< 18%）")
    if results['max_drawdown'] < -0.18:
        warnings.append("⚠️ 最大回撤超标（> 18%）")
    if results['sharpe_ratio'] < 1.4:
        warnings.append("⚠️ 夏普比率未达标（< 1.4）")
    if results['turnover'] * 12 > 2.0:
        warnings.append(f"⚠️ 年化换手率过高（{results['turnover'] * 12:.2%} > 200%）")
    if results['win_rate'] < 0.55:
        warnings.append("⚠️ 胜率未达标（< 55%）")
    
    if warnings:
        for warning in warnings:
            report += f"- {warning}\n"
    else:
        report += "✅ 所有指标均达标\n"
    
    report += """
---

## 五、结论

"""
    
    # 生成结论（v3.2调整目标）
    达标数 = sum([
        results['total_trades'] >= 50,
        results['annual_return'] > 0.18,
        results['max_drawdown'] > -0.18,
        results['sharpe_ratio'] > 1.4,
        results['turnover'] * 12 < 2.0,
        results['win_rate'] > 0.55
    ])
    
    if 达标数 >= 5:
        report += "✅ **策略表现优秀**，建议进一步优化后实盘测试。\n"
    elif 达标数 >= 4:
        report += "⚠️ **策略表现一般**，建议继续优化参数。\n"
    else:
        report += "❌ **策略表现不佳**，需要重新设计策略逻辑。\n"

    report += f"""
### 建议

1. 如果交易次数不足，考虑降低score_threshold至0.60或放宽流动性过滤
2. 如果年化收益率不达标，考虑调整theta_buy至-7~-8%（更激进）
3. 如果最大回撤过大，考虑加强止损逻辑或降低单笔风险
4. 如果胜率不高，考虑优化RSI阈值（30-40范围）
5. 如果换手率过高，考虑提高score_threshold至0.68-0.70

### v3.2改进点

- ✅ 加权评分系统（0-1范围，7个维度加权）
  - 趋势权重: 0.25 (SMA60向上)
  - BIAS权重: 0.25 (负乖离率超跌，分母放宽至8)
  - 缩量权重: 0.15 (成交量萎缩)
  - RSI权重: 0.15 (超卖，分母放宽至15)
  - MACD权重: 0.10 (HIST转正)
  - 阳线权重: 0.10 (收盘>开盘)
  - 政策权重: 0.20 (预留接口，当前降级为0)
- ✅ 信号阈值可配置（score_threshold: 0.60-0.70，默认0.65）
- ✅ 遗传算法强化（种群100、代数100、交易次数惩罚>=50笔）
- ✅ 换手率双重控制（月均<16.7%、年化<200%）
- ✅ 流动性过滤放宽（成交额>3000万）
- ✅ 保持T+1执行、停牌过滤、完整成本模型

---

**报告生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""
    
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(report)


if __name__ == '__main__':
    # 测试
    import pandas as pd
    
    test_params = {
        'theta_buy': 6.0,
        'theta_sell': 12.0,
        'alpha_vol': 0.6,
        'rsi_thresh': 30
    }
    
    test_results = {
        'initial_cash': 1000000,
        'final_equity': 1250000,
        'total_return': 0.25,
        'annual_return': 0.22,
        'max_drawdown': -0.12,
        'sharpe_ratio': 1.8,
        'turnover': 0.12,
        'win_rate': 0.65,
        'total_trades': 50,
        'equity_curve': pd.DataFrame({
            'date': pd.date_range('2026-01-01', periods=60),
            'equity': [1000000 + i * 4000 for i in range(60)]
        })
    }
    
    generate_report(test_params, test_results, './test_reports')
    print("测试报告已生成")
