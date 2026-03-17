from xtquant import xtdata

# 使用"沪深A股"板块，应该都是活跃股票
stocks = xtdata.get_stock_list_in_sector('沪深A股')
print(f"沪深A股: {len(stocks)}只")

# 测试前20只
test_stocks = stocks[:20]
print(f"\n测试 {len(test_stocks)} 只股票...")

for stock in test_stocks:
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
                print(f"{stock}: {price}")
            else:
                print(f"{stock}: 无数据")
    except Exception as e:
        print(f"{stock}: Error - {e}")
