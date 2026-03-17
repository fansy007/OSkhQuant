from xtquant import xtdata

stocks = ['600051.SH', '605090.SH', '600025.SH', '601222.SH', '688031.SH', '603335.SH', 
          '688045.SH', '603341.SH', '600967.SH', '603237.SH', '000001.SZ', '300003.SZ']

for stock in stocks:
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
