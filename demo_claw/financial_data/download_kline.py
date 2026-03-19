# -*- coding: utf-8 -*-
"""
下载创业板K线数据
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

# 下载K线数据
start_time = '20240101'
end_time = '20260319'

print(f"\n下载K线数据: {start_time} - {end_time}")
print(f"股票数量: {len(stock_list)}")

# 批量下载
try:
    xtdata.download_history_data2(
        stock_list=stock_list,
        period='1d',
        start_time=start_time,
        end_time=end_time
    )
    print("下载完成!")
except Exception as e:
    print(f"下载失败: {e}")

# 验证下载
print("\n验证下载...")
sample_stocks = stock_list[:5]
for stock in sample_stocks:
    data = xtdata.get_market_data_ex(
        field_list=['time', 'close'],
        stock_list=[stock],
        period='1d',
        start_time=start_time,
        end_time=end_time
    )
    if stock in data and data[stock] is not None:
        print(f"  {stock}: {len(data[stock])} 条数据")
    else:
        print(f"  {stock}: 无数据")
