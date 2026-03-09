# QuantV2 量化策略完整包

## 📦 包含内容

### 1. 方案文档 (docs/)
- `阶梯博弈与动态风险平价量化方案v1.md` - 策略核心方案
- `训练集.md` - 训练集选择方案（30只核心股票）

### 2. 代码文件 (code/)
- `config.py` - 配置文件（数据库、策略参数）
- `data_loader.py` - 数据加载模块
- `indicators.py` - 技术指标计算
- `signals.py` - 交易信号生成
- `position_sizing.py` - 仓位管理
- `backtest.py` - 回测引擎
- `wfo_optimizer.py` - WFO优化器
- `run_wfo_training.py` - 调参程序（训练集）
- `run_backtest.py` - 回测程序（测试集）
- `test_system.py` - 系统测试
- `requirements.txt` - Python依赖
- `README.md` - 代码说明
- `DELIVERY.md` - 交付文档

### 3. 调参结果 (results/)
- `wfo_training_results_20260309_205107.json` - WFO调参结果
- `wfo_training.log` - 调参日志

## 🎯 最佳参数（WFO调参结果）

**训练集期间**：2023-01-01 至 2024-01-01  
**测试集期间**：2024-01-01 至 2024-04-01

**最优参数组合**：
```python
{
    "theta_buy": 7.0,      # 负乖离率阈值
    "theta_sell": 10.0,    # 正乖离率阈值
    "alpha_vol": 0.4,      # 缩量系数
    "R": 0.02              # 单笔风险敞口2%
}
```

**训练集表现**：
- 总收益率：108.12%
- 年化收益率：113.08%
- 最大回撤：-7.08%
- Calmar比率：15.96
- 夏普比率：1.29

## 🚀 快速开始

### 1. 环境准备
```bash
cd code/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. 配置数据库
编辑 `config.py` 中的数据库连接信息：
```python
DB_CONFIG = {
    'host': '100.87.204.122',
    'port': 5432,
    'database': 'quant_db',
    'user': 'quant',
    'password': 'Quant@2025!Secure'
}
```

### 3. 运行回测
```bash
# 使用最优参数运行回测
python run_backtest.py
```

### 4. 重新调参（可选）
```bash
# 在训练集上重新调参
python run_wfo_training.py
```

## 📊 调参说明

### 训练集（30只核心股票）
- CPO/光模块：8只（中际旭创、新易盛等）
- 半导体/芯片：8只（菲利华、北方华创等）
- 人形机器人/国产算力：8只（优必选、寒武纪等）
- 液冷/海外算力：6只（工业富联、英维克等）

### WFO配置
- 训练窗口：12个月
- 测试窗口：3个月
- 参数空间：672个组合
- 优化目标：Calmar Ratio

## ⚠️ 注意事项

1. **数据库依赖**：需要连接到PostgreSQL数据库（quant_db）
2. **数据要求**：需要2023-2026年的日K线数据
3. **运行环境**：建议在副机（joe-tm1703）上运行调参程序
4. **时间窗口**：当前只完成了2个窗口，建议重新运行完整的5个窗口

## 📝 文件说明

### 调参结果文件格式
```json
{
  "wfo_results": [
    {
      "window": 1,
      "train_period": "20230101 - 20240101",
      "test_period": "20240101 - 20240401",
      "best_params": {...},
      "train_metrics": {...},
      "test_metrics": {...}
    }
  ],
  "summary": {...}
}
```

## 🔧 下一步工作

1. ✅ 完成训练集调参（已完成）
2. ⏳ 修复时间窗口配置（当前只有2个窗口）
3. ⏳ 使用最优参数对股票池进行回测
4. ⏳ 分析测试集无交易的原因
5. ⏳ 优化参数空间（增加交易频率）

## 📞 联系方式

- 开发时间：2026-03-09
- 开发者：Kiro (OpenClaw Agent)
- 用户：火锅

---

**版本**：v1.0  
**最后更新**：2026-03-09 21:00
