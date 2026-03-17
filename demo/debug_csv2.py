import pandas as pd
df = pd.read_csv('demo/financial_data/financial_data.csv')
stocks = ['300418.SZ', '300315.SZ', '300533.SZ', '300518.SZ']
for s in stocks:
    print(f"\n=== {s} ===")
    stock_df = df[df['stock_code'] == s]
    print(stock_df[['end_date', 'net_profit', 'net_cashflow_oper_act']])
