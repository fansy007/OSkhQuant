import pandas as pd
df = pd.read_csv('demo/financial_data/financial_data.csv')
print('CSV里的股票:', df['stock_code'].unique())
stocks = ['300418.SZ', '300315.SZ', '300533.SZ', '300518.SZ']
for s in stocks:
    if s in df['stock_code'].values:
        print(f'{s} 在CSV里')
    else:
        print(f'{s} 不在CSV里')
