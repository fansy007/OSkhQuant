# -*- coding: utf-8 -*-
"""检查财务数据字段"""
import sys
import os
import importlib
import importlib.util
import pandas as pd

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')

for key in list(sys.modules.keys()):
    if 'xtquant' in key:
        del sys.modules[key]

spec = importlib.util.spec_from_file_location('xtquant', os.path.join(XTQUANT_PATH, '__init__.py'))
xtquant = importlib.util.module_from_spec(spec)
sys.modules['xtquant'] = xtquant
spec.loader.exec_module(xtquant)

xtdata_spec = importlib.util.spec_from_file_location('xtquant.xtdata', os.path.join(XTQUANT_PATH, 'xtdata.py'))
xtdata = importlib.util.module_from_spec(xtdata_spec)
sys.modules['xtquant.xtdata'] = xtdata
xtdata_spec.loader.exec_module(xtdata)

# 下载一只股票的财务数据
stock_list = ['600519.SH']  # 茅台
xtdata.download_financial_data2(stock_list=stock_list, table_list=['Income', 'CashFlow'])

# 获取数据
income_data = xtdata.get_financial_data(
    stock_list=stock_list,
    table_list=['Income'],
    start_time='20220101',
    end_time='20251231'
)

print("数据结构:", income_data.keys())
if '600519.SH' in income_data:
    inner = income_data['600519.SH']
    print("inner keys:", inner.keys() if isinstance(inner, dict) else type(inner))
    if isinstance(inner, dict) and 'Income' in inner:
        df = inner['Income']
        print("\n列名:", df.columns.tolist())
        # 检查是否有非0的数据
print("\nrevenue_inc:", df['revenue_inc'].tolist())
print("revenue:", df['revenue'].tolist())
