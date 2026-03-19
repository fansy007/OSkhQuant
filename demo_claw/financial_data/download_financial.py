# -*- coding: utf-8 -*-
"""
下载创业板财务数据
"""
import sys
import os
import importlib.util

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', 'xtquant')

# 加载xtquant
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

# 获取创业板股票列表
print("获取创业板股票列表...")
stock_list = xtdata.get_stock_list_in_sector('创业板')
print(f"创业板股票数量: {len(stock_list)}")

# 下载财务数据
print("\n下载财务数据...")
print("表: Income, CashFlow")

try:
    xtdata.download_financial_data2(
        stock_list=stock_list,
        table_list=['Income', 'CashFlow']
    )
    print("下载完成!")
except Exception as e:
    print(f"下载失败: {e}")

# 验证下载
print("\n验证下载...")
sample_stocks = stock_list[:3]
for stock in sample_stocks:
    try:
        data = xtdata.get_financial_data(
            stock_list=[stock],
            table_list=['Income', 'CashFlow'],
            start_time='20230101',
            end_time='20251231',
            report_type='announce_time'
        )
        if stock in data:
            tables = data[stock]
            income_count = len(tables.get('Income', []))
            cashflow_count = len(tables.get('CashFlow', []))
            print(f"  {stock}: Income={income_count}条, CashFlow={cashflow_count}条")
        else:
            print(f"  {stock}: 无数据")
    except Exception as e:
        print(f"  {stock}: 获取失败 - {e}")
