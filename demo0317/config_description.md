# 交易配置文件说明

本文档描述了买入(`buy_config.txt`)和卖出(`sell_config.txt`)条件配置文件的逻辑。

---

## 一、买入条件 (buy_config.txt)

### 1.1 行业过滤

```txt
industry,创业板
```

**逻辑**：只选择特定行业的股票。

- 当前配置：`创业板`
- 支持的行业名称需通过xtquant获取（如"创业板"、"科创板"等）

### 1.2 技术指标 - 换手率

```txt
turnover,10,5,2
```

**逻辑**：筛选活跃度足够的股票

| 参数 | 值 | 说明 |
|------|-----|------|
| 第1个 | 10 | 统计天数（过去10个交易日） |
| 第2个 | 5 | 单日换手率阈值（%） |
| 第3个 | 2 | 日均换手率阈值（%） |

**筛选条件**：
1. 统计过去N天内，换手率超过 `pct_min` 的天数
2. 计算这N天的日均换手率
3. 同时满足：超过阈值天数>0 且 日均换手率>avg_min

### 1.3 买入门槛

```txt
min_buy_amount,50000
```

**逻辑**：账户现金超过此金额才进行买入（单位：元）

### 1.4 财务指标 - 静态条件

```txt
s_revenue,>,100000000
s_oper_profit,>,10000000
s_net_profit_incl_min_int_inc_after,>,100000000
```

**格式**：`s_字段,比较符,值`

**逻辑**：取最新已发布的Q4年报数据，与固定值比较

| 字段 | 中文名 | 表 |
|------|--------|-----|
| revenue | 营业总收入 | Income |
| oper_profit | 营业利润 | Income |
| net_profit_incl_min_int_inc_after | 净利润(扣除非经常性损益后) | Income |

**支持的比较符**：`>`, `<`, `>=`, `<=`, `=`

### 1.5 财务指标 - 动态条件

```txt
d_revenue,>,2
d_net_profit_incl_min_int_inc_after,>,2
d_adjusted_net_profit_rate,>,2
```

**格式**：`d_字段,比较符,N`

**逻辑**：最新一期与前N年同期比较，连续N年增长

例如 `d_revenue,>,2` 表示：
- 取最近3年同季度（如Q4）的营收数据
- 验证：2024 Q4 > 2023 Q4 > 2022 Q4（连续2年增长）

**支持的字段**：
| 字段 | 中文名 | 表 |
|------|--------|-----|
| revenue | 营业总收入 | Income |
| oper_profit | 营业利润 | Income |
| net_profit_incl_min_int_inc | 净利润(含非经常性损益) | Income |
| net_profit_incl_min_int_inc_after | 净利润(扣除非经常性损益后) | Income |
| net_cash_flows_oper_act | 经营活动产生的现金流量净额 | CashFlow |
| du_return_on_equity | 净资产收益率 | PershareIndex |
| inc_revenue_rate | 主营收入同比增长 | PershareIndex |
| adjusted_net_profit_rate | 扣非净利润同比增长 | PershareIndex |
| gross_profit | 毛利率 | PershareIndex |
| net_profit | 净利率 | PershareIndex |
| gear_ratio | 资产负债比率 | PershareIndex |

---

## 二、卖出条件 (sell_config.txt)

### 2.1 止损

```txt
stop_loss,12.0
```

**逻辑**：
- 当持仓股从最高点回撤超过 `12%` 时触发止损
- 公式：`(peak_price - current_price) / peak_price * 100 >= stop_loss`
- 每天收盘后检查

### 2.2 止盈

```txt
take_profit,12.0
```

**逻辑**：
- 当持仓股盈利达到 `12%` 时触发止盈
- 公式：`(current_price - cost) / cost * 100 >= take_profit`
- 每天收盘后检查

### 2.3 再平衡（调仓）

```txt
rebalance_days,10
```

**逻辑**：
- 每隔 `10` 个交易日进行一次再平衡
- 在再平衡日：
  1. 卖出：不在新选股名单中的持仓股
  2. 买入：用卖出资金买入新选出的股票

### 2.4 基准对比

```txt
benchmark,399006.SZ
```

**逻辑**：
- 对比的指数代码（当前为创业板指数）
- 用于后续生成策略绩效报告时与基准对比

---

## 三、完整配置示例

### buy_config.txt
```txt
# 买入条件配置文件

# 行业条件
industry,创业板

# 技术指标
turnover,10,5,2

# 买入门槛
min_buy_amount,50000

# 财务指标 - 静态条件（Q4年报与固定值比较）
s_revenue,>,100000000
s_oper_profit,>,10000000
s_net_profit_incl_min_int_inc_after,>,100000000

# 财务指标 - 动态条件（连续N年增长）
d_revenue,>,2
d_net_profit_incl_min_int_inc_after,>,2
d_adjusted_net_profit_rate,>,2
```

### sell_config.txt
```txt
# 卖出条件配置文件

# 止损（回撤比例%）
stop_loss,12.0

# 止盈（盈利比例%）
take_profit,12.0

# 再平衡周期（天）
rebalance_days,10

# 基准指数
benchmark,399006.SZ
```

---

## 四、执行优先级

### 买入执行顺序
1. **行业过滤** → 获取行业内的股票列表
2. **技术指标筛选** → 按换手率过滤
3. **财务指标筛选** → 按静态/动态条件过滤
4. **获取收盘价** → 获取当日收盘价用于下单
5. **资金分配** → 根据 `min_buy_amount` 判断是否执行买入

### 卖出执行顺序（每日）
1. **止损检查** → 每天检查，触发则卖出
2. **止盈检查** → 每天检查，触发则卖出
3. **调仓检查** → 仅在调仓日检查，不在新名单则卖出
