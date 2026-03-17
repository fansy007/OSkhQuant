# -*- coding: utf-8 -*-
"""检查CashFlow字段"""
import sys, os, importlib, importlib.util

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')

for key in list(sys.modules.keys()):
    if 'xtquant' in key: del sys.modules[key]

spec = importlib.util.spec_from_file_location('xtquant', os.path.join(XTQUANT_PATH, '__init__.py'))
xtquant = importlib.util.module_from_spec(spec)
sys.modules['xtquant'] = xtquant
spec.loader.exec_module(xtquant)

xtdata_spec = importlib.util.spec_from_file_location('xtquant.xtdata', os.path.join(XTQUANT_PATH, 'xtdata.py'))
xtdata = importlib.util.module_from_spec(xtdata_spec)
sys.modules['xtquant.xtdata'] = xtdata
xtdata_spec.loader.exec_module(xtdata)

# 下载并获取CashFlow
stock_list = ['600519.SH']
xtdata.download_financial_data2(stock_list=stock_list, table_list=['CashFlow'])

cashflow_data = xtdata.get_financial_data(
    stock_list=stock_list,
    table_list=['CashFlow'],
    start_time='20220101',
    end_time='20251231'
)

if '600519.SH' in cashflow_data:
    inner = cashflow_data['600519.SH']
    if isinstance(inner, dict) and 'CashFlow' in inner:
        df = inner['CashFlow']
        print("CashFlow列名:", df.columns.tolist())
        print("\n数据:")
        print(df.head(3))
