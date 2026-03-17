# 调试日期匹配
QUARTER_DATE = {'q1': '0331', 'q2': '0630', 'q3': '0930', 'q4': '1231'}
CURRENT_YEAR = 2025

def get_date_from_quarter(quarter: str, year: int) -> str:
    q_date = QUARTER_DATE.get(quarter.lower(), '1231')
    return f"{year}{q_date}"

# 配置条件
net_profit_conds = [('q4', '>', 100000000.0, 0), ('q3', '>', 1, 1)]

print("配置条件:")
for quarter, op, value, periods in net_profit_conds:
    if periods == 0:
        date = get_date_from_quarter(quarter, CURRENT_YEAR - 1)
        print(f"  q4静态: {date}")
    else:
        dates = []
        for i in range(periods):
            year = CURRENT_YEAR - i
            dates.append(get_date_from_quarter(quarter, year))
        print(f"  q3动态{periods}期: {dates}")

print("\nCSV中的日期:")
import pandas as pd
df = pd.read_csv('demo/financial_data/financial_data.csv')
stock_df = df[df['stock_code'] == '300315.SZ']
for _, row in stock_df.tail(5).iterrows():
    print(f"  {row['end_date']} net_profit={row['net_profit']:.2e}")
