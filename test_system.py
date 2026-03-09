"""
测试脚本：验证数据库连接和基本功能
"""

import sys
sys.path.insert(0, '/tmp/quantv2_strategy')

def test_database_connection():
    """测试数据库连接"""
    print("=" * 60)
    print("测试1: 数据库连接")
    print("=" * 60)

    try:
        from data_loader import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM kline_daily")
        count = cursor.fetchone()[0]
        print(f"✓ 数据库连接成功")
        print(f"✓ kline_daily表共有 {count:,} 条记录")
        conn.close()
        return True
    except Exception as e:
        print(f"✗ 数据库连接失败: {e}")
        return False


def test_stock_list():
    """测试股票列表加载"""
    print("\n" + "=" * 60)
    print("测试2: 股票列表加载")
    print("=" * 60)

    try:
        from data_loader import load_stock_list
        stocks = load_stock_list()
        print(f"✓ 成功加载 {len(stocks)} 只股票")
        if len(stocks) > 0:
            print(f"  示例: {stocks[:5]}")
        return True
    except Exception as e:
        print(f"✗ 股票列表加载失败: {e}")
        return False


def test_load_single_stock():
    """测试单只股票数据加载"""
    print("\n" + "=" * 60)
    print("测试3: 单只股票数据加载")
    print("=" * 60)

    try:
        from data_loader import load_stock_list, load_stock_data
        stocks = load_stock_list()

        if len(stocks) == 0:
            print("✗ 没有可用股票")
            return False

        test_stock = stocks[0]
        df = load_stock_data(test_stock)

        print(f"✓ 成功加载 {test_stock} 数据")
        print(f"  数据行数: {len(df)}")
        print(f"  日期范围: {df.index[0]} 至 {df.index[-1]}")
        print(f"  列名: {list(df.columns)}")
        return True
    except Exception as e:
        print(f"✗ 股票数据加载失败: {e}")
        return False


def test_indicators():
    """测试技术指标计算"""
    print("\n" + "=" * 60)
    print("测试4: 技术指标计算")
    print("=" * 60)

    try:
        from data_loader import load_stock_list, load_stock_data
        from indicators import calculate_all_indicators

        stocks = load_stock_list()
        if len(stocks) == 0:
            print("✗ 没有可用股票")
            return False

        test_stock = stocks[0]
        df = load_stock_data(test_stock)
        df = calculate_all_indicators(df)

        required_cols = ['SMA_20', 'SMA_60', 'BIAS_20', 'ATR_14', 'Vol_SMA_10']
        missing = [col for col in required_cols if col not in df.columns]

        if missing:
            print(f"✗ 缺少指标列: {missing}")
            return False

        print(f"✓ 技术指标计算成功")
        print(f"  新增列: {[col for col in df.columns if col not in ['open', 'high', 'low', 'close', 'volume', 'amount']]}")
        return True
    except Exception as e:
        print(f"✗ 技术指标计算失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_signals():
    """测试信号生成"""
    print("\n" + "=" * 60)
    print("测试5: 交易信号生成")
    print("=" * 60)

    try:
        from data_loader import load_stock_list, load_stock_data
        from indicators import calculate_all_indicators
        from signals import generate_signals

        stocks = load_stock_list()
        if len(stocks) == 0:
            print("✗ 没有可用股票")
            return False

        test_stock = stocks[0]
        df = load_stock_data(test_stock)
        df = calculate_all_indicators(df)
        df = generate_signals(df)

        buy_count = df['buy_signal'].sum()
        sell_count = df['sell_signal'].sum()

        print(f"✓ 信号生成成功")
        print(f"  买入信号数: {buy_count}")
        print(f"  卖出信号数: {sell_count}")
        return True
    except Exception as e:
        print(f"✗ 信号生成失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == '__main__':
    print("\n量化策略系统测试\n")

    results = []
    results.append(("数据库连接", test_database_connection()))
    results.append(("股票列表", test_stock_list()))
    results.append(("数据加载", test_load_single_stock()))
    results.append(("技术指标", test_indicators()))
    results.append(("信号生成", test_signals()))

    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name:12s}: {status}")

    passed = sum(1 for _, r in results if r)
    total = len(results)

    print(f"\n总计: {passed}/{total} 通过")

    if passed == total:
        print("\n✓ 所有测试通过！系统可以运行。")
    else:
        print("\n✗ 部分测试失败，请检查配置。")
