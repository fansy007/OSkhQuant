# -*- coding: utf-8 -*-
import pandas as pd
df = pd.read_csv(r'e:\workspace\OSkhQuant\demo\financial_data\financial_data.csv')

# 查看000526的2024年报现金流
stock = df[df['stock_code'] == '000526.SZ']
print('000526.SZ 2024年数据:')
print(stock[stock['end_date'].astype(str).str.contains('2024')])

# 查看有现金流的数据
print('\n有现金流的记录示例:')
cf = df[df['net_cashflow_oper_act'].notna()].head(5)
print(cf[['stock_code', 'end_date', 'net_profit', 'net_cashflow_oper_act']])
