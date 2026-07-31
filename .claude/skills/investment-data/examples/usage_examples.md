# 使用示例

## 基础示例

### 1. 查询单只股票

```python
from scripts.data_client import InvestmentData

client = InvestmentData()

# 查询平安银行 2024 年数据
df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")

print(df.head())
```

输出：
```
    ts_code trade_date   open   high    low  close      vol    amount
0  000001.SZ 2024-01-02  12.34  12.89  12.10  12.56   123.45  1234.56
1  000001.SZ 2024-01-03  12.50  12.98  12.32  12.78   145.67  1456.78
...
```

### 2. 批量查询

```python
stocks = ["000001.SZ", "000002.SZ", "600000.SH"]

for stock in stocks:
    df = client.get_stock_daily(stock, "2024-01-01", "2024-12-31")
    df.to_csv(f"{stock}.csv", index=False)
```

### 3. 导出 Excel

```python
client.export_data(
    "000001.SZ",
    "2024-01-01",
    "2024-12-31",
    "output.xlsx",
    format="excel"
)
```

## 高级示例

### 1. 计算收益率

```python
import pandas as pd

# 查询数据
df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")

# 计算日收益率
df['return'] = df['close'].pct_change()

# 计算累计收益率
df['cum_return'] = (1 + df['return']).cumprod()

print(df[['trade_date', 'close', 'return', 'cum_return']].tail())
```

### 2. 指数成分分析

```python
# 查询沪深 300 成分权重
weights = client.get_index_weights("000300.SH", date="2024-12-31")

# 筛选权重前 10
top_10 = weights.nlargest(10, 'weight')

print(top_10)
```

### 3. 涨跌停分析

```python
from datetime import datetime, timedelta

# 查询最近 30 天涨跌停情况
end_date = datetime.now().strftime("%Y-%m-%d")
start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

df = client.get_stock_daily("000001.SZ", start_date, end_date)

# 查询涨跌停信息
for date in df['trade_date']:
    limit_info = client.get_limit_data("000001.SZ", date)
    if limit_info['limit_status'] != 'normal':
        print(f"{date}: {limit_info['limit_status']}")
```

### 4. 批量导出多只股票

```python
import pandas as pd
from concurrent.futures import ThreadPoolExecutor

def export_stock(stock_code):
    df = client.get_stock_daily(stock_code, "2024-01-01", "2024-12-31")
    df.to_csv(f"./data/{stock_code}.csv", index=False)
    return stock_code

# 读取股票列表
stocks = pd.read_csv("stocks.txt", header=None)[0].tolist()

# 并发导出
with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(export_stock, stocks))

print(f"已导出 {len(results)} 只股票")
```

## 命令行示例

### 查询并导出

```bash
# 查询单只股票
python scripts/query.py --stock 000001.SZ --start 2024-01-01 --end 2024-12-31

# 导出为 CSV
python scripts/query.py --stock 000001.SZ --start 2024-01-01 --end 2024-12-31 --output output.csv

# 导出为 Excel
python scripts/query.py --stock 000001.SZ --start 2024-01-01 --end 2024-12-31 --output output.xlsx --format excel
```

### 批量查询

```bash
# 创建股票列表文件
cat > stocks.txt << EOF
000001.SZ
000002.SZ
600000.SH
EOF

# 批量查询（需要实现 query_batch.py）
python scripts/query_batch.py --file stocks.txt --start 2024-01-01 --end 2024-12-31 --output ./data/
```

## 自动化示例

### 定时更新

```python
import schedule
import time
from scripts.data_client import InvestmentData

def daily_update():
    client = InvestmentData()
    client.update_data()
    print("数据更新完成")

# 每天早上 9:00 更新
schedule.every().day.at("09:00").do(daily_update)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### OpenClaw 集成

```yaml
# .openclaw/cron.yaml
jobs:
  - name: "每日更新股票数据"
    schedule: "0 9 * * *"
    command: "python scripts/update_data.py --daily"
```

## 数据分析示例

### 1. 计算技术指标

```python
import pandas as pd
import numpy as np

df = client.get_stock_daily("000001.SZ", "2024-01-01", "2024-12-31")

# MA5
df['ma5'] = df['close'].rolling(window=5).mean()

# MA20
df['ma20'] = df['close'].rolling(window=20).mean()

# RSI (14)
delta = df['close'].diff()
gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
rs = gain / loss
df['rsi'] = 100 - (100 / (1 + rs))

print(df[['trade_date', 'close', 'ma5', 'ma20', 'rsi']].tail())
```

### 2. 波动率分析

```python
# 计算日收益率
df['return'] = df['close'].pct_change()

# 计算年化波动率
volatility = df['return'].std() * np.sqrt(252)

print(f"年化波动率: {volatility:.2%}")
```

### 3. 相关性分析

```python
# 查询多只股票
stocks = ["000001.SZ", "000002.SZ", "600000.SH"]
data = {}

for stock in stocks:
    df = client.get_stock_daily(stock, "2024-01-01", "2024-12-31")
    data[stock] = df['close']

# 构建价格矩阵
price_df = pd.DataFrame(data)

# 计算相关性
correlation = price_df.pct_change().corr()

print(correlation)
```
