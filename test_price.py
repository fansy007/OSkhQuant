from xtquant import xtdata
import pandas as pd

# 测试获取股价
stocks = ['600036.SH', '000001.SZ', '300003.SZ']

for stock in stocks:
    print(f"\n=== {stock} ===")
    try:
        result = xtdata.get_market_data(
            stock_list=[stock],
            start_time="20250317",
            end_time="20250317",
            count=1
        )
        print(f"返回类型: {type(result)}")
        if result:
            print(f"Keys: {list(result.keys())}")
            if 'close' in result:
                close = result['close']
                print(f"close类型: {type(close)}")
                print(f"close形状: {close.shape}")
                print(f"close数据:\n{close}")
    except Exception as e:
        print(f"Error: {e}")
