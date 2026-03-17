from xtquant import xtdata

# 测试不同板块的股票数量
sectors_to_test = [
    '沪深A股',
    '沪深京A股', 
    '创业板',
    '上证A股',
    '深证A股',
    '科创板',
    '沪市A股',
    '深市A股',
    '沪深B股',
]

print("=== 各板块股票数量 ===")
for sector in sectors_to_test:
    try:
        result = xtdata.get_stock_list_in_sector(sector)
        count = len(result) if result else 0
        print(f"{sector}: {count}只")
        if result and count <= 10:
            print(f"  股票: {result}")
    except Exception as e:
        print(f"{sector}: Error - {e}")
