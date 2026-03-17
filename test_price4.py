from xtquant import xtdata

# 试试用"沪深京A股"，然后测试一些靠后的股票
stocks = xtdata.get_stock_list_in_sector('沪深京A股')

# 随机测试一些靠后的股票
test_indices = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 4500, 5000]

for idx in test_indices:
    if idx < len(stocks):
        stock = stocks[idx]
        try:
            result = xtdata.get_market_data(
                stock_list=[stock],
                start_time="20250317",
                end_time="20250317",
                count=1
            )
            if result and 'close' in result:
                close_df = result['close']
                if not close_df.empty and close_df.shape[1] > 0:
                    price = close_df.iloc[0, 0]
                    print(f"[{idx}] {stock}: {price}")
                else:
                    print(f"[{idx}] {stock}: 无数据")
        except Exception as e:
            print(f"[{idx}] {stock}: Error")
