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


def generate_report(params: dict, results: dict, output_dir: str = None):
    """
    生成回测报告
    
    Parameters:
    -----------
    params : dict
        策略参数
    results : dict
        回测结果
    output_dir : str
        输出目录
    """
    if output_dir is None:
        output_dir = REPORT_CONFIG['output_dir']
    
    os.makedirs(output_dir, exist_ok=True)
    
    logger.info("=" * 80)
    logger.info("生成回测报告")
    logger.info("=" * 80)
    
    # 生成净值曲线图
    equity_curve_path = os.path.join(output_dir, 'equity_curve.png')
    plot_equity_curve(results['equity_curve'], equity_curve_path)
    logger.info(f"✓ 净值曲线图: {equity_curve_path}")
    
    # 生成Markdown报告
    report_path = os.path.join(output_dir, 'backtest_report.md')
    write_markdown_report(params, results, report_path)
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


def write_markdown_report(params: dict, results: dict, output_path: str):
    """
    生成Markdown报告
    
    Parameters:
    -----------
    params : dict
        策略参数
    results : dict
        回测结果
    output_path : str
        输出路径
    """
    report = f"""# 量化策略回测报告

**生成时间**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## 一、策略参数

| 参数 | 值 | 说明 |
|------|-----|------|
| theta_buy | {params.get('theta_buy', 'N/A')} | 买入乖离率阈值（%） |
| theta_sell | {params.get('theta_sell', 'N/A')} | 卖出乖离率阈值（%） |
| alpha_vol | {params.get('alpha_vol', 'N/A')} | 缩量系数 |
| rsi_thresh | {params.get('rsi_thresh', 'N/A')} | RSI阈值 |

---

## 二、回测指标

### 2.1 收益指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 初始资金 | {results['initial_cash']:,.0f} 元 | - | - |
| 最终权益 | {results['final_equity']:,.0f} 元 | - | - |
| 总收益率 | {results['total_return']:.2%} | - | - |
| 年化收益率 | {results['annual_return']:.2%} | > 20% | {'✅' if results['annual_return'] else '❌'} |

### 2.2 风险指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 最大回撤 | {results['max_drawdown']:.2%} | < 15% | {'✅' if results['max_drawdown'] > -0.15 else '❌'} |
| 夏普比率 | {results['sharpe_ratio']:.2f} | > 1.5 | {'✅' if results['sharpe_ratio'] > 1.5 else '❌'} |

### 2.3 交易指标

| 指标 | 值 | 目标 | 达标 |
|------|-----|------|------|
| 换手率 | {results['turnover']:.2f}/月 | < 15%/月 | {'✅' if results['turnover'] < 0.15 else '❌'} |
| 胜率 | {results['win_rate']:.2%} | > 60% | {'✅' if results['win_rate'] > 0.60 else '❌'} |
| 总交易次数 | {results['total_trades']} | - | - |

---

## 三、净值曲线
![净值曲线](equity_curve.png)

---

## 四、风险分析

### 4.1 收益风险比

- **Calmar比率**: {results['annual_return'] / abs(results['max_drawdown']) if results['max_drawdown'] != 0 else 0:.2f}
- **收益回撤比**: {results['total_return'] / abs(results['max_drawdown']) if results['max_drawdown'] != 0 else 0:.2f}

### 4.2 风险提示

"""

    # 添加风险提示
    warnings = []
    if results['annual_return'] < 0.20:
        warnings.append("⚠️ 年化收益率未达标（< 20%）")
    if results['max_drawdown'] < -0.15:
        warnings.append("⚠️ 最大回撤超标（> 15%）")
    if results['sharpe_ratio'] < 1.5:
        warnings.append("⚠️ 夏普比率未达标（< 1.5）")
    if results['turnover'] > 0.15:
        warnings.append("⚠️ 换手率过高（> 15%/月）")
    if results['win_rate'] < 0.60:
        warnings.append("⚠️ 胜率未达标（< 60%）")
    
    if warnings:
        for warning in warnings:
            report += f"- {warning}\n"
    else:
        report += "✅ 所有指标均达标\n"
    
    report += """
---

## 五、结论

"""
    
    # 生成结论
    达标数 = sum([
        results['annual_return'] > 0.20,
        results['max_drawdown'] > -0.15,
        results['sharpe_ratio'] > 1.5,
        results['turnover'] < 0.15,
        results['win_rate'] > 0.60
    ])
    
    if 达标数 >= 4:
        report += "✅ **策略表现优秀**，建议进一步优化后实盘测试。\n"
    elif 达标数 >= 3:
        report += "⚠️ **策略表现一般**，建议继续优化参数。\n"
    else:
        report += "❌ **策略表现不佳**，需要重新设计策略逻辑。\n"
    
    report += f"""
### 建议

1. 如果年化收益率不达标，考虑放宽买入条件或优化参数
2. 如果最大回撤过大，考虑加强止损逻辑
3. 如果胜率不高，考虑优化买点选择
4. 如果换手率过高，考虑延长持仓周期

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
