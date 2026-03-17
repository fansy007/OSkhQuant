# 检查选出的股票的财务数据
import sys, os, importlib, importlib.util
import pandas as pd

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')

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

# 换手率筛选后的4只股票
stocks = ['300418.SZ', '300315.SZ', '300533.SZ', '300518.SZ']

print("下载财务数据...")
xtdata.download_financial_data2(stock_list=stocks, table_list=['Income', 'CashFlow'])

# 获取净利润数据
income_data = xtdata.get_financial_data(
    stock_list=stocks,
    table_list=['Income'],
    start_time='20200101',
    end_time='20251231'
)

print("\n=== 净利润数据 ===")
for stock in stocks:
    inc = income_data.get(stock, {}).get('Income', pd.DataFrame())
    if not inc.empty and 'm_timetag' in inc.columns:
        print(f"\n{stock}:")
        cols = ['m_timetag', 'net_profit_incl_min_int_inc']
        available_cols = [c for c in cols if c in inc.columns]
        if available_cols:
            print(inc[available_cols].tail(6))
        else:
            print(inc.columns.tolist()[:10])
