# Investment Data Skill

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://clawhub.com)
[![License](https://img.shields.io/badge/license-Apache--2.0-green.svg)](LICENSE)

高质量 A 股投资数据获取工具，基于 [investment_data](https://github.com/chenditc/investment_data) 项目。

## ✨ 特性

- 🚀 **开箱即用** - 一键下载最新数据
- 📊 **高质量数据** - 多数据源交叉验证
- 🔄 **每日更新** - 自动化 CI/CD 流程
- 📈 **完整性好** - 包含退市公司数据
- 🛠️ **多格式支持** - Qlib、CSV、JSON、Excel
- 🔌 **OpenClaw 集成** - 支持自动化工作流

## 📥 安装

### 方法 1：通过 ClawHub（推荐）

```bash
clawhub install investment-data
```

### 方法 2：手动安装

```bash
git clone https://github.com/StanleyChanH/investment-data-skill.git
cd investment-data-skill
pip install -r requirements.txt
```

## 🚀 快速开始

### 1. 下载最新数据

```bash
python scripts/download_data.py --latest
```

### 2. 查询股票数据

#### Python API

```python
from scripts.data_client import InvestmentData

client = InvestmentData()

# 查询股票日 K 线
df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")
print(df.head())

# 查询指数
index_df = client.get_index_daily("000300.SH", "2024-01-01", "2024-12-31")

# 查询涨跌停
limits = client.get_limit_data("000001.SZ", date="2024-12-01")
```

#### 命令行

```bash
# 查询单只股票
python scripts/query.py --stock 000001.SZ --start 2024-01-01 --end 2024-12-31

# 批量查询
python scripts/query_batch.py --file stocks.txt --start 2024-01-01 --output json

# 导出 Excel
python scripts/export.py --stock 000001.SZ --format excel
```

## 📊 数据类型

### 1. 日终价格（final_a_stock_eod_price）

| 字段 | 说明 | 类型 |
|------|------|------|
| ts_code | 股票代码 | str |
| trade_date | 交易日期 | date |
| open | 开盘价 | float |
| high | 最高价 | float |
| low | 最低价 | float |
| close | 收盘价 | float |
| vol | 成交量（万手） | float |
| amount | 成交额（千元） | float |
| adj_factor | 复权因子 | float |

### 2. 涨跌停数据（final_a_stock_limit）

| 字段 | 说明 | 类型 |
|------|------|------|
| ts_code | 股票代码 | str |
| trade_date | 交易日期 | date |
| up_limit | 涨停价 | float |
| down_limit | 跌停价 | float |
| limit_status | 涨跌停状态 | str |

## 🔧 配置

### 环境变量

```bash
# 数据存储路径
export INVESTMENT_DATA_DIR=~/.qlib/qlib_data/cn_data

# Tushare Token（可选）
export TUSHARE_TOKEN=your_token_here
```

### 配置文件

编辑 `config/config.yaml`：

```yaml
data:
  data_dir: ~/.qlib/qlib_data/cn_data
  auto_update: true
  update_time: "09:00"

query:
  output_format: csv
  date_format: "%Y-%m-%d"
```

## 📝 使用示例

### 批量查询导出

```python
from scripts.data_client import InvestmentData
import pandas as pd

client = InvestmentData()

# 读取股票列表
stocks = pd.read_csv("stocks.txt", header=None)[0].tolist()

# 批量查询
for stock in stocks:
    df = client.get_stock_daily(stock, "2024-01-01", "2024-12-31")
    df.to_csv(f"./data/{stock}.csv", index=False)
```

### 指数成分分析

```python
# 查询沪深 300 成分
weights = client.get_index_weights("000300.SH", date="2024-12-31")

# 筛选权重前 10
top_10 = weights.nlargest(10, 'weight')
print(top_10)
```

## 🔄 自动化

### OpenClaw 定时任务

```yaml
# 每天早上 9:00 更新数据
schedule:
  cron: "0 9 * * *"
  task: "python scripts/update_data.py --daily"
```

### 批量处理工作流

```python
# 自动化脚本
import schedule
import time

def daily_update():
    client = InvestmentData()
    client.update_data()

schedule.every().day.at("09:00").do(daily_update)

while True:
    schedule.run_pending()
    time.sleep(60)
```

## 📖 API 文档

### InvestmentData 类

#### `__init__(data_dir=None)`
初始化客户端

**参数**：
- `data_dir` (str, optional): 数据目录路径

#### `get_stock_daily(ts_code, start_date, end_date)`
查询股票日 K 线数据

**参数**：
- `ts_code` (str): 股票代码（如 "000001.SZ"）
- `start_date` (str): 开始日期（如 "2024-01-01"）
- `end_date` (str): 结束日期（如 "2024-12-31"）

**返回**：
- `pd.DataFrame`: 日 K 线数据

#### `get_index_daily(ts_code, start_date, end_date)`
查询指数数据

#### `get_limit_data(ts_code, date)`
查询涨跌停数据

#### `get_stock_list(date)`
查询股票列表

#### `update_data()`
更新数据到最新版本

## ⚠️ 注意事项

1. **数据延迟**：T+1 数据，每日更新
2. **存储空间**：需要约 5GB
3. **网络要求**：需访问 GitHub
4. **Tushare Token**：实时更新需要

## 🤝 贡献

欢迎贡献代码、报告问题或提出建议！

### 开发环境

```bash
git clone https://github.com/StanleyChanH/investment-data-skill.git
cd investment-data-skill
pip install -r requirements.txt
python -m pytest tests/
```

## 📄 许可证

Apache License 2.0

## 🙏 致谢

- [chenditc/investment_data](https://github.com/chenditc/investment_data) - 原始数据项目
- [dmnsn7](https://github.com/dmnsn7) - 提供 Tushare token

## 📚 相关资源

- **GitHub**：https://github.com/StanleyChanH/investment-data-skill
- **原始项目**：https://github.com/chenditc/investment_data
- **DoltHub**：https://www.dolthub.com/repositories/chenditc/investment_data
- **ClawHub**：https://clawhub.com/skill/investment-data
