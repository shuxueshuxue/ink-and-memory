#!/usr/bin/env python3
"""
投资数据客户端

基于 investment_data 项目，提供高质量 A 股投资数据查询接口
"""

import os
import pandas as pd
import numpy as np
from pathlib import Path
from typing import Optional, List, Union
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class InvestmentData:
    """投资数据客户端"""

    def __init__(self, data_dir: Optional[str] = None):
        """
        初始化客户端

        Args:
            data_dir: 数据目录路径，默认为 ~/.qlib/qlib_data/cn_data
        """
        self.data_dir = Path(data_dir or os.getenv(
            'INVESTMENT_DATA_DIR',
            Path.home() / '.qlib' / 'qlib_data' / 'cn_data'
        ))

        if not self.data_dir.exists():
            logger.warning(f"数据目录不存在: {self.data_dir}")
            logger.info("请先运行: python scripts/download_data.py --latest")

        # 数据文件路径
        self.stock_data_file = self.data_dir / "features" / "day" / "data.bin"
        self.limit_data_file = self.data_dir / "features" / "limit" / "data.bin"
        self.index_data_dir = self.data_dir / "inc2group"

    def get_stock_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        查询股票日 K 线数据

        Args:
            ts_code: 股票代码（如 "000001.SZ"）
            start_date: 开始日期（如 "2024-01-01"）
            end_date: 结束日期（如 "2024-12-31"）

        Returns:
            pd.DataFrame: 日 K 线数据
        """
        # TODO: 实现从 Qlib 二进制文件读取数据
        # 这里先返回示例数据
        logger.info(f"查询股票数据: {ts_code} ({start_date} ~ {end_date})")

        dates = pd.date_range(start_date, end_date, freq='B')  # 工作日
        n = len(dates)

        data = {
            'ts_code': ts_code,
            'trade_date': dates,
            'open': np.random.uniform(10, 20, n),
            'high': np.random.uniform(15, 25, n),
            'low': np.random.uniform(8, 18, n),
            'close': np.random.uniform(12, 22, n),
            'vol': np.random.uniform(100, 1000, n),
            'amount': np.random.uniform(1000, 10000, n),
        }

        return pd.DataFrame(data)

    def get_index_daily(
        self,
        ts_code: str,
        start_date: str,
        end_date: str
    ) -> pd.DataFrame:
        """
        查询指数数据

        Args:
            ts_code: 指数代码（如 "000300.SH"）
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            pd.DataFrame: 指数日 K 线数据
        """
        logger.info(f"查询指数数据: {ts_code} ({start_date} ~ {end_date})")
        # TODO: 实现指数数据查询
        return pd.DataFrame()

    def get_limit_data(
        self,
        ts_code: str,
        date: str
    ) -> dict:
        """
        查询涨跌停数据

        Args:
            ts_code: 股票代码
            date: 交易日期

        Returns:
            dict: 涨跌停信息
        """
        logger.info(f"查询涨跌停: {ts_code} {date}")
        # TODO: 实现涨跌停数据查询
        return {
            'ts_code': ts_code,
            'trade_date': date,
            'up_limit': 20.0,
            'down_limit': 10.0,
            'limit_status': 'normal'
        }

    def get_stock_list(self, date: Optional[str] = None) -> List[str]:
        """
        查询股票列表

        Args:
            date: 交易日期，默认为最新

        Returns:
            List[str]: 股票代码列表
        """
        logger.info(f"查询股票列表: {date or 'latest'}")
        # TODO: 实现股票列表查询
        return ['000001.SZ', '000002.SZ', '600000.SH']

    def get_index_weights(
        self,
        index_code: str,
        date: Optional[str] = None
    ) -> pd.DataFrame:
        """
        查询指数成分权重

        Args:
            index_code: 指数代码
            date: 交易日期

        Returns:
            pd.DataFrame: 成分权重数据
        """
        logger.info(f"查询指数成分: {index_code} {date or 'latest'}")
        # TODO: 实现指数成分查询
        return pd.DataFrame()

    def update_data(self) -> bool:
        """
        更新数据到最新版本

        Returns:
            bool: 是否更新成功
        """
        logger.info("更新数据...")
        # 调用下载脚本
        import subprocess
        result = subprocess.run(
            ['python', 'scripts/download_data.py', '--latest'],
            capture_output=True,
            text=True
        )
        return result.returncode == 0

    def export_data(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        output_file: str,
        format: str = 'csv'
    ) -> bool:
        """
        导出数据到文件

        Args:
            ts_code: 股票代码
            start_date: 开始日期
            end_date: 结束日期
            output_file: 输出文件路径
            format: 输出格式（csv, json, excel）

        Returns:
            bool: 是否导出成功
        """
        df = self.get_stock_daily(ts_code, start_date, end_date)

        if format == 'csv':
            df.to_csv(output_file, index=False)
        elif format == 'json':
            df.to_json(output_file, orient='records', indent=2)
        elif format == 'excel':
            df.to_excel(output_file, index=False)
        else:
            raise ValueError(f"不支持的格式: {format}")

        logger.info(f"数据已导出到: {output_file}")
        return True


if __name__ == "__main__":
    # 示例用法
    client = InvestmentData()

    # 查询股票数据
    df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")
    print(df.head())

    # 导出数据
    client.export_data(
        "000001.SZ",
        "2024-01-01",
        "2024-12-31",
        "output.csv",
        format="csv"
    )
