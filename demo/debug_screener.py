# -*- coding: utf-8 -*-
"""调试选股逻辑"""
import pandas as pd

CSV_PATH = r'e:\workspace\OSkhQuant\demo\financial_data\financial_data.csv'
df = pd.read_csv(CSV_PATH)

# 报表日期
report_dates = {
    '2025_mid': '20250630',
    '2025_q3': '20250930',
    '2024_q3': '20240930',
    '2024_annual': '20241231',
}

# 检查每只股票
for stock in df['stock_code'].unique()[:5]:
    stock_df = df[df['stock_code'] == stock]
    stock_df = stock_df.copy()
    stock_df['end_date'] = stock_df['end_date'].astype(str)
    
    print(f"\n=== {stock} ===")
    
    def get_val(date_str, field):
        row = stock_df[stock_df['end_date'] == date_str]
        if row.empty:
            return None
        val = row[field].iloc[0]
        return val if pd.notna(val) else None
    
    # 打印各期数据
    print(f"2025中报净利润: {get_val(report_dates['2025_mid'], 'net_profit')}")
    print(f"2025三季报净利润: {get_val(report_dates['2025_q3'], 'net_profit')}")
    print(f"2024三季报净利润: {get_val(report_dates['2024_q3'], 'net_profit')}")
    print(f"2025三季报营收: {get_val(report_dates['2025_q3'], 'operating_revenue')}")
    print(f"2024三季报营收: {get_val(report_dates['2024_q3'], 'operating_revenue')}")
    print(f"2024年报净利润: {get_val(report_dates['2024_annual'], 'net_profit')}")
    print(f"2024年报现金流: {get_val(report_dates['2024_annual'], 'net_cashflow_oper_act')}")
    
    # 检查条件
    net_2025_mid = get_val(report_dates['2025_mid'], 'net_profit')
    net_2025_q3 = get_val(report_dates['2025_q3'], 'net_profit')
    net_2024_q3 = get_val(report_dates['2024_q3'], 'net_profit')
    rev_2025_q3 = get_val(report_dates['2025_q3'], 'operating_revenue')
    rev_2024_q3 = get_val(report_dates['2024_q3'], 'operating_revenue')
    net_2024 = get_val(report_dates['2024_annual'], 'net_profit')
    cf_2024 = get_val(report_dates['2024_annual'], 'net_cashflow_oper_act')
    
    print("条件检查:")
    print(f"  1. 2025中报净利润>0: {net_2025_mid} -> {net_2025_mid > 0 if net_2025_mid else 'N/A'}")
    print(f"  2. 2025三季报>{' '}2024三季报: {net_2025_q3} > {net_2024_q3} = {net_2025_q3 > net_2024_q3 if (net_2025_q3 and net_2024_q3) else 'N/A'}")
    print(f"  3. 营收增长: {rev_2025_q3} > {rev_2024_q3} = {rev_2025_q3 > rev_2024_q3 if (rev_2025_q3 and rev_2024_q3) else 'N/A'}")
    print(f"  4. 2024净利润>1亿: {net_2024} > 1亿 = {net_2024 > 1e8 if net_2024 else 'N/A'}")
    print(f"  5. 2024现金流>1亿: {cf_2024} > 1亿 = {cf_2024 > 1e8 if cf_2024 else 'N/A'}")
