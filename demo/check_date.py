# -*- coding: utf-8 -*-
import pandas as pd
df = pd.read_csv(r'e:\workspace\OSkhQuant\demo\financial_data\financial_data.csv')

# 查看2024年所有的日期
df_2024 = df[df['end_date'].astype(str).str.contains('2024')]
print('2024年的日期:')
print(df_2024['end_date'].unique())

# 查看有现金流的记录
print('\n有现金流的记录:')
cf = df[df['net_cashflow_oper_act'].notna()]
print(cf['end_date'].unique())
