#!/usr/bin/env python3
"""
基础测试
"""

import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_client import InvestmentData


def test_init():
    """测试初始化"""
    client = InvestmentData()
    assert client is not None
    print("✅ 初始化测试通过")


def test_get_stock_daily():
    """测试股票数据查询"""
    client = InvestmentData()
    df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-01-31")

    assert df is not None
    assert len(df) > 0
    assert 'ts_code' in df.columns
    assert 'trade_date' in df.columns
    assert 'close' in df.columns

    print("✅ 股票数据查询测试通过")


def test_get_stock_list():
    """测试股票列表查询"""
    client = InvestmentData()
    stocks = client.get_stock_list()

    assert stocks is not None
    assert len(stocks) > 0
    assert "000001.SZ" in stocks

    print("✅ 股票列表查询测试通过")


if __name__ == "__main__":
    test_init()
    test_get_stock_daily()
    test_get_stock_list()

    print("\n✅ 所有测试通过！")
