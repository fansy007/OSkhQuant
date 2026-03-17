# -*- coding: utf-8 -*-
"""
下载五年财务数据并存入CSV - 修复版本
"""
import sys
import os
import importlib
import importlib.util
from datetime import datetime, timedelta
import pandas as pd

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')
CSV_PATH = os.path.join(PROJECT_ROOT, 'demo', 'financial_data')


def load_xtquant():
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
    
    return xtquant, xtdata


def download_financial_data(xtdata, stock_list: list):
    os.makedirs(CSV_PATH, exist_ok=True)
    
    # 下载财务数据
    print("下载财务数据...")
    try:
        xtdata.download_financial_data2(
            stock_list=stock_list,
            table_list=['Income', 'CashFlow']
        )
        print("下载完成")
    except Exception as e:
        print(f"下载出错: {e}")
        return
    
    # 获取财务数据
    print("读取财务数据...")
    income_data = xtdata.get_financial_data(
        stock_list=stock_list,
        table_list=['Income'],
        start_time='20200101',
        end_time='20251231'
    )
    
    cashflow_data = xtdata.get_financial_data(
        stock_list=stock_list,
        table_list=['CashFlow'],
        start_time='20200101',
        end_time='20251231'
    )
    
    # 处理并保存
    all_records = []
    
    for stock in stock_list:
        print(f"处理 {stock}...")
        
        income = income_data.get(stock, {}).get('Income', pd.DataFrame())
        cashflow = cashflow_data.get(stock, {}).get('CashFlow', pd.DataFrame())
        
        # 合并现金流数据到Income
        if not income.empty and not cashflow.empty:
            # 将现金流数据合并到Income
            income = income.copy()
            income['end_date'] = income['m_timetag'].astype(str)
            cashflow = cashflow.copy()
            cashflow['end_date'] = cashflow['m_timetag'].astype(str)

            # 提取现金流字段 - xtquant返回的字段名是 net_cash_flows_oper_act
            cf_fields = [col for col in cashflow.columns if 'net_cash_flows_oper_act' in col]
            if cf_fields:
                cf_df = cashflow[['end_date', cf_fields[0]]].rename(
                    columns={cf_fields[0]: 'net_cashflow_oper_act'})
                # 合并
                income = income.merge(cf_df, on='end_date', how='left')
        
        if not income.empty and 'revenue_inc' in income.columns:
            for _, row in income.iterrows():
                date = str(row.get('m_timetag', ''))
                record = {
                    'stock_code': stock,
                    'end_date': date,
                    'operating_revenue': row.get('revenue_inc', row.get('revenue', None)),
                    'net_profit': row.get('net_profit_incl_min_int_inc', row.get('net_profit', None)),
                    'net_cashflow_oper_act': row.get('net_cashflow_oper_act', None),
                }
                all_records.append(record)
    
    if all_records:
        df = pd.DataFrame(all_records)
        
        # 直接保存，忽略旧数据
        csv_file = os.path.join(CSV_PATH, 'financial_data.csv')
        df.to_csv(csv_file, index=False, encoding='utf-8-sig')
        
        print(f"\n已保存到: {csv_file}")
        print(f"共 {len(df)} 条记录, {df['stock_code'].nunique()} 只股票")
        print(df.tail(10))
    else:
        print("无数据")


def main():
    print("=" * 60)
    print(" 财务数据下载工具")
    print("=" * 60)
    
    xtquant, xtdata = load_xtquant()
    print("xtquant 加载成功")
    
    # 获取所有38只股票
    industry = "SW3移动互联网服务"
    stock_list = xtdata.get_stock_list_in_sector(industry)
    print(f"\n行业 '{industry}' 共有 {len(stock_list)} 只股票")
    
    download_financial_data(xtdata, stock_list)


if __name__ == "__main__":
    main()
