#!/usr/bin/env python3
"""
投资数据下载脚本

从 GitHub Release 下载最新的 investment_data 数据集
"""

import os
import sys
import argparse
import requests
import tarfile
from pathlib import Path
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)


def get_latest_release() -> str:
    """获取最新 release 版本"""
    url = "https://api.github.com/repos/chenditc/investment_data/releases/latest"
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
    return data['tag_name']


def download_file(url: str, output_path: str) -> bool:
    """下载文件"""
    try:
        logger.info(f"正在下载: {url}")
        response = requests.get(url, stream=True)
        response.raise_for_status()

        total_size = int(response.headers.get('content-length', 0))

        with open(output_path, 'wb') as f:
            if total_size == 0:
                f.write(response.content)
            else:
                downloaded = 0
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        # 显示进度
                        percent = (downloaded / total_size) * 100
                        sys.stdout.write(f"\r下载进度: {percent:.1f}%")
                        sys.stdout.flush()

        print()  # 换行
        logger.info(f"下载完成: {output_path}")
        return True

    except Exception as e:
        logger.error(f"下载失败: {e}")
        return False


def extract_tar(tar_path: str, output_dir: str) -> bool:
    """解压 tar.gz 文件"""
    try:
        logger.info(f"正在解压: {tar_path}")
        with tarfile.open(tar_path, 'r:gz') as tar:
            tar.extractall(path=output_dir)
        logger.info(f"解压完成: {output_dir}")
        return True
    except Exception as e:
        logger.error(f"解压失败: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description='下载 investment_data 数据集')
    parser.add_argument(
        '--latest',
        action='store_true',
        help='下载最新版本'
    )
    parser.add_argument(
        '--version',
        type=str,
        help='指定版本（如 2026-02-13）'
    )
    parser.add_argument(
        '--output',
        type=str,
        default=None,
        help='输出目录（默认为 ~/.qlib/qlib_data/cn_data）'
    )
    parser.add_argument(
        '--keep-tar',
        action='store_true',
        help='保留 tar.gz 文件'
    )

    args = parser.parse_args()

    # 确定版本
    if args.latest:
        version = get_latest_release()
        logger.info(f"最新版本: {version}")
    elif args.version:
        version = args.version
    else:
        logger.error("请指定 --latest 或 --version")
        sys.exit(1)

    # 输出目录
    output_dir = Path(args.output or Path.home() / '.qlib' / 'qlib_data' / 'cn_data')
    output_dir.mkdir(parents=True, exist_ok=True)

    # 下载 URL
    tar_filename = "qlib_bin.tar.gz"
    download_url = f"https://github.com/chenditc/investment_data/releases/download/{version}/{tar_filename}"

    # 临时文件路径
    temp_tar = output_dir / tar_filename

    # 下载
    if not download_file(download_url, temp_tar):
        sys.exit(1)

    # 解压
    if not extract_tar(temp_tar, output_dir):
        sys.exit(1)

    # 清理
    if not args.keep_tar:
        temp_tar.unlink()
        logger.info(f"已删除临时文件: {temp_tar}")

    logger.info(f"✅ 数据下载完成！")
    logger.info(f"数据目录: {output_dir}")
    logger.info(f"版本: {version}")


if __name__ == "__main__":
    main()
