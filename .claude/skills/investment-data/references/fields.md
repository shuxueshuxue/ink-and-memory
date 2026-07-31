# 数据字段说明

## 1. 日终价格数据（final_a_stock_eod_price）

### 基础字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| ts_code | str | 股票代码 | "000001.SZ" |
| trade_date | date | 交易日期 | 2024-01-15 |
| open | float | 开盘价 | 12.34 |
| high | float | 最高价 | 12.89 |
| low | float | 最低价 | 12.10 |
| close | float | 收盘价 | 12.56 |
| vol | float | 成交量（万手） | 1234.56 |
| amount | float | 成交额（千元） | 12345.67 |

### 复权字段

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| adj_factor | float | 复权因子 | 1.2345 |
| adj_open | float | 前复权开盘价 | 15.23 |
| adj_high | float | 前复权最高价 | 15.89 |
| adj_low | float | 前复权最低价 | 14.92 |
| adj_close | float | 前复权收盘价 | 15.48 |

## 2. 涨跌停数据（final_a_stock_limit）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| ts_code | str | 股票代码 | "000001.SZ" |
| trade_date | date | 交易日期 | 2024-01-15 |
| up_limit | float | 涨停价 | 13.82 |
| down_limit | float | 跌停价 | 11.30 |
| limit_status | str | 涨跌停状态 | "up_limit" |
| pre_close | float | 前收盘价 | 12.56 |

### 涨跌停状态说明

- `normal`: 正常交易
- `up_limit`: 涨停
- `down_limit`: 跌停
- `suspended`: 停牌

## 3. 指数数据（index_daily）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| index_code | str | 指数代码 | "000300.SH" |
| trade_date | date | 交易日期 | 2024-01-15 |
| open | float | 开盘点位 | 3512.34 |
| high | float | 最高点位 | 3534.89 |
| low | float | 最低点位 | 3500.10 |
| close | float | 收盘点位 | 3523.56 |
| vol | float | 成交量（万手） | 123456.78 |
| amount | float | 成交额（千元） | 1234567.89 |

## 4. 指数成分权重（index_weight）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| index_code | str | 指数代码 | "000300.SH" |
| trade_date | date | 交易日期 | 2024-01-15 |
| constituent_code | str | 成分股代码 | "000001.SZ" |
| weight | float | 权重（%） | 1.23 |

## 5. 股票列表（stock_list）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| ts_code | str | 股票代码 | "000001.SZ" |
| name | str | 股票名称 | "平安银行" |
| list_date | date | 上市日期 | 1991-04-03 |
| delist_date | date | 退市日期 | None |
| market | str | 市场类型 | "主板" |
| status | str | 上市状态 | "L"（上市） |

### 上市状态说明

- `L`: 上市
- `D`: 退市
- `P`: 暂停上市

## 6. 复权因子（adj_factor）

| 字段名 | 类型 | 说明 | 示例 |
|--------|------|------|------|
| ts_code | str | 股票代码 | "000001.SZ" |
| trade_date | date | 交易日期 | 2024-01-15 |
| adj_factor | float | 复权因子 | 1.2345 |

### 复权计算

- **前复权价格** = 原始价格 × 复权因子
- **复权因子**：以上市首日为基准（1.0），之后每次除权除息调整

## 数据质量

### 数据源优先级

1. **final**: 最终修正数据（最高优先级）
2. **ts**: Tushare 数据
3. **ak**: Akshare 数据
4. **yahoo**: Yahoo Finance 数据
5. **baostock**: Baostock 数据

### 数据验证

- **交叉验证**：多数据源对比
- **异常检测**：自动识别异常值
- **缺失填补**：从其他数据源补充
- **退市数据**：完整保留退市公司历史数据

## 注意事项

1. **成交量单位**：万手（除以 100 得到手数）
2. **成交额单位**：千元（除以 1000 得到万元）
3. **复权价格**：使用 `adj_factor` 字段进行复权
4. **数据延迟**：T+1 更新（今天看到昨天的完整数据）
5. **退市股票**：保留完整历史数据，`status` 字段为 "D"
