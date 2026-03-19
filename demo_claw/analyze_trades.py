import pandas as pd

df = pd.read_csv(r'E:\workspace\OSkhQuant\demo_claw\output\backtest_trades.csv')
sells = df[df['action']=='SELL']

print("=== 卖出统计 ===")
print("总卖出次数:", len(sells))
print("盈利次数:", len(sells[sells['profit']>0]))
print("亏损次数:", len(sells[sells['profit']<=0]))
print("胜率:", round(len(sells[sells['profit']>0])/len(sells)*100, 1), "%")
print()

total_profit = sells['profit'].sum()
print("总盈亏:", int(total_profit))
print("最大盈利:", int(sells['profit'].max()))
print("最大亏损:", int(sells['profit'].min()))
print("平均盈利:", int(sells[sells['profit']>0]['profit'].mean()))
print("平均亏损:", int(sells[sells['profit']<=0]['profit'].mean()))
print()

# 盈亏比
avg_win = sells[sells['profit']>0]['profit'].mean()
avg_loss = abs(sells[sells['profit']<=0]['profit'].mean())
print("盈亏比:", round(avg_win/avg_loss, 2))

print()
print("=== TOP10盈利单 ===")
wins = sells[sells['profit']>0].sort_values('profit', ascending=False).head(10)
for _, row in wins.iterrows():
    print(f"  {row['stock']} | 日期:{row['date']} | 盈利:{int(row['profit'])}")

print()
print("=== TOP10亏损单 ===")
losses = sells[sells['profit']<=0].sort_values('profit').head(10)
for _, row in losses.iterrows():
    print(f"  {row['stock']} | 日期:{row['date']} | 亏损:{int(row['profit'])}")
