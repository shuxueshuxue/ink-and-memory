#!/usr/bin/env python3
"""
投资数据查询脚本
"""

import argparse
import sys
from pathlib import Path

# 添加父目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.data_client import InvestmentData


def main():
    parser = argparse.ArgumentParser(description='查询投资数据')
    parser.add_argument(
        '--stock',
        type=str,
        required=True,
        help='股票代码（如 000001.SZ）'
    )
    parser.add_argument(
        '--start',
        type=str,
        required=True,
        help='开始日期（如 2024-01-01）'
    )
    parser.add_argument(
        '--end',
        type=str,
        required=True,
        help='结束日期（如 2024-12-31）'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='输出文件路径'
    )
    parser.add_argument(
        '--format',
        type=str,
        default='csv',
        choices=['csv', 'json', 'excel'],
        help='输出格式'
    )

    args = parser.parse_args()

    # 初始化客户端
    client = InvestmentData()

    # 查询数据
    df = client.get_stock_daily(args.stock, args.start, args.end)

    # 输出
    if args.output:
        client.export_data(
            args.stock,
            args.start,
            args.end,
            args.output,
            args.format
        )
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
