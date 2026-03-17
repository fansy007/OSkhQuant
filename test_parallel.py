import sys
import os
sys.path.insert(0, r'e:\workspace\OSkhQuant')

from demo0317.financial_analysis.get_financial import get_pe_pb_data_parallel, get_all_stocks
import time

# 获取全部股票并过滤（只保留沪深A股，排除北交所BJ）
all_stocks = get_all_stocks()
# 过滤：排除北交所(.BJ)，只保留沪市(.SH)和深市(.SZ)
filtered_stocks = [s for s in all_stocks if s.endswith('.SH') or s.endswith('.SZ')]
print(f"过滤后: {len(filtered_stocks)} 只股票（排除北交所）")

# 测试前10只
test_stocks = filtered_stocks[:10]
print(f"测试股票: {test_stocks}")

print(f"\n测试 {len(test_stocks)} 只股票...")
start = time.time()
df = get_pe_pb_data_parallel(test_stocks, years=5, num_threads=5)
elapsed = time.time() - start

print(f"\n结果:")
print(df)
print(f"\n耗时: {elapsed:.1f} 秒")
print(f"成功: {len(df)}/{len(test_stocks)} 只")
