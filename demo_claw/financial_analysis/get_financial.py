# -*- coding: utf-8 -*-
"""
个股基本面数据获取模块
输入: 股票代码数组
输出: 5年基本面信息
"""
import sys
import os
import importlib
from datetime import datetime
import pandas as pd

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')


def load_xtquant():
    """手动加载xtquant"""
    for key in list(sys.modules.keys()):
        if 'xtquant' in key:
            del sys.modules[key]

    spec = importlib.util.spec_from_file_location('xtquant', os.path.join(XTQUANT_PATH, '__init__.py'))
    xtquant = importlib.util.module_from_spec(spec)
    sys.modules['xtquant'] = xtquant
    spec.loader.exec_module(xtquant)

    xtdata_spec = importlib.util.spec_from_file_location('xtquant.xtdata', os.path.join(XTQUANT_PATH, 'xtdata.py'))
    xtdata = importlib.util.module_from_spec(xtdata_spec)
    sys.modules['xtquant.xtdata'] = xtdata
    xtdata_spec.loader.exec_module(xtdata)

    return xtquant, xtdata


# 字段映射表 (field: (中文名, 表名))
FIELD_MAPPING = {
    # ========== 利润表 (Income) ==========
    'revenue': ('营业总收入', 'Income'),
    'oper_profit': ('营业利润', 'Income'),
    'net_profit_incl_min_int_inc_after': ('净利润(扣除非经常性损益后)', 'Income'),
    # ========== 现金流量表 (CashFlow) ==========
    'net_cash_flows_oper_act': ('经营活动产生的现金流量净额', 'CashFlow'),
    'net_cash_flows_inv_act': ('投资活动产生的现金流量净额', 'CashFlow'),
    'net_cash_flows_fnc_act': ('筹资活动产生的现金流量净额', 'CashFlow'),
    # ========== 每股指标 (PershareIndex) ==========
    'du_return_on_equity': ('净资产收益率', 'PershareIndex'),
    'inc_revenue_rate': ('主营收入同比增长', 'PershareIndex'),
    'adjusted_net_profit_rate': ('扣非净利润同比增长', 'PershareIndex'),
    'gross_profit': ('毛利率', 'PershareIndex'),
    'net_profit': ('净利率', 'PershareIndex'),
    'gear_ratio': ('资产负债比率', 'PershareIndex'),
}


def get_financial_data(stock_list: list, years: int = 5) -> pd.DataFrame:
    """
    获取个股基本面数据

    Args:
        stock_list: 股票代码列表
        years: 获取近几年数据，默认5年

    Returns:
        DataFrame with fields: stock, year, table, field, value
    """
    xtquant, xtdata = load_xtquant()
    print(f"xtquant 加载成功")

    # 计算时间范围
    current_year = datetime.now().year
    start_year = current_year - years
    start_time = f'{start_year}0101'
    end_time = f'{current_year}1231'

    # 报表类型列表
    table_list = ['Income', 'CashFlow', 'PershareIndex']

    # 获取财务数据
    print(f"获取财务数据: {stock_list}")
    result = xtdata.get_financial_data(
        stock_list=stock_list,
        table_list=table_list,
        start_time=start_time,
        end_time=end_time,
        report_type='announce_time'
    )

    print(f"返回数据类型: {type(result)}")
    if result:
        print(f"股票列表: {list(result.keys())}")

    if not result:
        print("无数据返回")
        return pd.DataFrame()

    # 解析返回数据 {stock: {table: DataFrame}}
    data_rows = []
    for stock, tables in result.items():
        for table_name, df in tables.items():
            if df is None or df.empty:
                continue

            # 日期列可能是 endDate 或 m_timetag
            date_col = 'endDate' if 'endDate' in df.columns else 'm_timetag'
            if date_col not in df.columns:
                print(f"  {stock} {table_name}: 无日期列, 列名: {list(df.columns)[:5]}...")
                continue

            for _, row in df.iterrows():
                # 获取年报期
                end_date = row.get(date_col, '')
                if not end_date:
                    continue
                # m_timetag 可能是时间戳或日期字符串
                if isinstance(end_date, (int, float)):
                    # 时间戳转日期
                    try:
                        end_date = datetime.fromtimestamp(end_date / 1000).strftime('%Y%m%d')
                    except:
                        continue
                elif not isinstance(end_date, str):
                    continue
                year = end_date[:4]

                # 遍历需要的字段
                for field, (cn_name, expected_table) in FIELD_MAPPING.items():
                    if expected_table != table_name:
                        continue

                    if field in df.columns:
                        value = row.get(field)
                        # 处理NaN
                        if pd.isna(value):
                            value = None
                        data_rows.append({
                            'stock': stock,
                            'year': year,
                            'table': table_name,
                            'field': field,
                            'value': value
                        })

    df_result = pd.DataFrame(data_rows)
    print(f"获取到 {len(df_result)} 条记录")
    return df_result


def filter_fields(df: pd.DataFrame) -> pd.DataFrame:
    """过滤出需要的字段"""
    if df.empty:
        return df
    return df[df['field'].isin(FIELD_MAPPING.keys())]


def print_financial_report(df: pd.DataFrame):
    """打印基本面报告"""
    if df.empty:
        print("\n无数据")
        return

    # 过滤关键字段
    df = filter_fields(df)
    if df.empty:
        print("\n无关键字段数据")
        return

    # 获取股票列表
    stocks = df['stock'].unique()

    for stock in stocks:
        stock_df = df[df['stock'] == stock]
        years = sorted(stock_df['year'].unique(), reverse=True)

        print(f"\n{'='*80}")
        print(f"股票: {stock}")
        print(f"{'='*80}")

        # 打印表头
        print(f"\n{'年份':<8}", end='')
        for field, (cn_name, table) in FIELD_MAPPING.items():
            print(f"{cn_name[:10]:<12}", end='')
        print()
        print('-' * 130)

        # 打印数据
        for year in years:
            year_df = stock_df[stock_df['year'] == year]
            year_data = dict(zip(year_df['field'], year_df['value']))

            print(f"{year:<8}", end='')
            for field, (cn_name, table) in FIELD_MAPPING.items():
                value = year_data.get(field)
                if value is None:
                    print(f"{'N/A':<12}", end='')
                elif field in ['du_return_on_equity', 'inc_revenue_rate', 'adjusted_net_profit_rate',
                               'gross_profit', 'net_profit', 'gear_ratio']:
                    print(f"{value:>10.2f}% ", end='')
                elif field in ['revenue', 'oper_profit', 'net_profit_incl_min_int_inc_after',
                               'net_cash_flows_oper_act', 'net_cash_flows_inv_act', 'net_cash_flows_fnc_act']:
                    # 转换为亿
                    print(f"{value/1e8:>10.2f}亿 ", end='')
                else:
                    print(f"{value:<12}", end='')
            print()


def export_to_csv(df: pd.DataFrame, output_path: str = None):
    """导出到CSV"""
    if df.empty:
        print("无数据可导出")
        return

    # 过滤关键字段
    df = filter_fields(df)

    # 转换为宽表格式
    if not df.empty:
        df_pivot = df.pivot_table(
            index=['stock', 'year'],
            columns='field',
            values='value',
            aggfunc='first'
        ).reset_index()

        # 添加中文列名
        rename_dict = {field: info[0] for field, info in FIELD_MAPPING.items()}
        df_pivot = df_pivot.rename(columns=rename_dict)

        if output_path is None:
            output_path = os.path.join(os.path.dirname(__file__), 'financial_analysis.csv')

        df_pivot.to_csv(output_path, index=False, encoding='utf-8-sig')
        print(f"\n数据已导出到: {output_path}")
        return df_pivot


def get_current_price(xtdata, stock: str) -> float:
    """获取股票最新收盘价"""
    try:
        result = xtdata.get_market_data(
            stock_list=[stock],
            start_time="20250101",
            end_time="20250317",
            count=1
        )
        # 返回格式是dict: {'close': DataFrame, 'open': DataFrame, ...}
        if result and 'close' in result:
            close_df = result['close']
            # DataFrame: index是股票代码，columns是日期
            if not close_df.empty:
                # 取最后一列（最新日期）
                latest_price = close_df.iloc[0, -1]
                print(f"    原始价格: {close_df.iloc[0, :]}")  # 调试
                return float(latest_price)
    except Exception as e:
        print(f"  获取 {stock} 股价失败: {e}")
    return None


def get_year_end_price(xtdata, stock: str, year: int) -> float:
    """获取某年年末（12月31日或其后的第一个交易日）的股价"""
    # 尝试12月31日附近的日子
    dates_to_try = [
        f"{year}1231",
        f"{year}1230",
        f"{year}1229",
        f"{year}1227",
        f"{year}1228",
    ]
    for date_str in dates_to_try:
        try:
            result = xtdata.get_market_data(
                stock_list=[stock],
                start_time=date_str,
                end_time=date_str,
                count=1
            )
            if result and 'close' in result:
                close_df = result['close']
                if not close_df.empty:
                    # DataFrame: index是股票代码，columns是日期
                    price = close_df.iloc[0, 0]
                    if price and price > 0:
                        print(f"      {date_str} 股价: {price}")
                        return float(price)
        except Exception as e:
            print(f"      {date_str} 失败: {e}")
            continue
    return None


def get_pe_pb_data(stock_list: list, years: int = 5) -> pd.DataFrame:
    """
    获取PE、PB及历史百分位
    
    Returns:
        DataFrame: 包含当前PE/PB、历史PE/PB序列、历史百分位
    """
    xtquant, xtdata = load_xtquant()
    print(f"xtquant 加载成功")
    
    current_year = datetime.now().year
    start_year = current_year - years
    
    results = []
    
    for stock in stock_list:
        print(f"\n处理: {stock}")
        
        # 1. 获取当前股价
        current_price = get_current_price(xtdata, stock)
        print(f"  当前股价: {current_price}")
        
        if current_price is None:
            print(f"  无法获取股价，跳过")
            continue
        
        # 2. 获取财务数据（PershareIndex表有EPS和BPS）
        try:
            fin_result = xtdata.get_financial_data(
                stock_list=[stock],
                table_list=['PershareIndex'],
                start_time=f'{start_year}0101',
                end_time=f'{current_year}1231',
                report_type='announce_time'
            )
        except Exception as e:
            print(f"  获取财务数据失败: {e}")
            continue
        
        if not fin_result or stock not in fin_result:
            print(f"  无财务数据")
            continue
        
        pershare = fin_result[stock].get('PershareIndex')
        if pershare is None or pershare.empty:
            print(f"  无PershareIndex数据")
            continue
        
        # 3. 解析财务数据，找出每年的年报数据
        # 注意：每年4月发布上一年年报，所以2025年3月应该用2023年年报
        # m_timetag格式: 20241231 表示2024年年报
        eps_dict = {}  # {year: eps}
        bps_dict = {}  # {year: bps}
        
        date_col = 'm_timetag'
        if 'endDate' in pershare.columns:
            date_col = 'endDate'
        
        for _, row in pershare.iterrows():
            end_date = row.get(date_col, '')
            if not end_date:
                continue
            # 处理时间戳
            if isinstance(end_date, (int, float)):
                try:
                    end_date = datetime.fromtimestamp(end_date / 1000).strftime('%Y%m%d')
                except:
                    continue
            if not isinstance(end_date, str):
                continue
            
            # 财报期年份（如202412表示2024年年报）
            report_year = end_date[:4]
            eps = row.get('s_fa_eps_basic')
            bps = row.get('s_fa_bps')
            
            # 存储每年的数据
            if eps and pd.notna(eps):
                eps_dict[report_year] = eps
            if bps and pd.notna(bps):
                bps_dict[report_year] = bps
        
        print(f"  财务年份: {list(eps_dict.keys())}")
        
        # 4. 计算当前PE/PB（用最新已发布的年报）
        # 2025年3月时，2024年年报还没发布，用2023年年报
        # 取最新发布的年报（非当年，因为当年年报还没发布）
        available_years = sorted([int(y) for y in eps_dict.keys()])
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        # 找最新可用年报：如果是上半年，用前两年；下半年用前一年
        if current_month < 5:  # 上半年（年报发布季）
            latest_report_year = current_year - 2
        else:  # 下半年
            latest_report_year = current_year - 1
        
        # 找到最接近latest_report_year的数据
        latest_year = None
        for y in sorted(eps_dict.keys(), reverse=True):
            if int(y) <= latest_report_year:
                latest_year = y
                break
        
        if not latest_year:
            print(f"  无可用年报数据")
            continue
            
        latest_eps = eps_dict[latest_year]
        latest_bps = bps_dict.get(latest_year, None)
        
        current_pe = round(current_price / latest_eps, 2) if latest_eps and latest_eps > 0 else None
        current_pb = round(current_price / latest_bps, 2) if latest_bps and latest_bps > 0 else None
        
        print(f"  使用{latest_year}年报: EPS={latest_eps}, BPS={latest_bps}")
        print(f"  当前PE: {current_pe}, PB: {current_pb}")
        
        # 5. 计算历史PE/PB（用之前各年年末股价）
        pe_history = []
        pb_history = []
        
        # 从latest_year往前，取之前3-5年的数据
        for year in sorted(eps_dict.keys()):
            if int(year) >= int(latest_year):
                continue  # 跳过当前年和之后的数据
            
            year_end_price = get_year_end_price(xtdata, stock, int(year))
            if year_end_price:
                eps = eps_dict[year]
                bps = bps_dict.get(year, None)
                
                if eps and eps > 0:
                    pe = year_end_price / eps
                    pe_history.append(round(pe, 2))
                    print(f"    {year}年末: 股价={year_end_price}, EPS={eps}, PE={pe:.2f}")
                
                if bps and bps > 0:
                    pb = year_end_price / bps
                    pb_history.append(round(pb, 2))
        
        current_pe = round(current_price / latest_eps, 2) if latest_eps and latest_eps > 0 else None
        current_pb = round(current_price / latest_bps, 2) if latest_bps and latest_bps > 0 else None
        
        print(f"  当前PE: {current_pe}, PB: {current_pb}")
        
        # 6. 计算历史百分位
        def calc_percentile(value, history):
            """计算百分位：当前值在历史序列中的位置"""
            if not history or value is None or len(history) < 2:
                return None
            # 百分位 = (当前值 - 最小值) / (最大值 - 最小值)
            # 或者用排名的百分比
            sorted_history = sorted(history)
            rank = sum(1 for v in sorted_history if v <= value)
            percentile = (rank / len(sorted_history)) * 100
            return round(percentile, 1)
        
        pe_percentile = calc_percentile(current_pe, pe_history)
        pb_percentile = calc_percentile(current_pb, pb_history)
        
        print(f"  PE历史百分位: {pe_percentile}% (历史PE: {pe_history})")
        print(f"  PB历史百分位: {pb_percentile}% (历史PB: {pb_history})")
        
        # 计算总市值
        try:
            info = xtdata.get_instrument_detail(stock)
            total_volume = info.get('TotalVolume', 0) if info else 0
            market_cap = round(current_price * total_volume / 1e8, 2) if total_volume else None
            print(f"  总市值: {market_cap}亿元")
        except Exception as e:
            market_cap = None
            print(f"  获取市值失败: {e}")
        
        results.append({
            'stock': stock,
            'current_price': current_price,
            'latest_year': latest_year,
            'eps': latest_eps,
            'bps': latest_bps,
            'pe': current_pe,
            'pb': current_pb,
            'pe_history': str(pe_history),
            'pb_history': str(pb_history),
            'pe_percentile': pe_percentile,
            'pb_percentile': pb_percentile,
            'market_cap': market_cap
        })
    
    return pd.DataFrame(results)


def export_pe_pb_csv(df: pd.DataFrame, output_path: str = None):
    """导出PE/PB数据到CSV"""
    if df.empty:
        print("无数据可导出")
        return
    
    if output_path is None:
        output_path = os.path.join(os.path.dirname(__file__), 'pe_pb_analysis.csv')
    
    df.to_csv(output_path, index=False, encoding='utf-8-sig')
    print(f"\nPE/PB数据已导出到: {output_path}")


import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time

# 全局结果存储（线程安全）
_results_lock = threading.Lock()
_pe_pb_results = []


def process_stock_batch(stocks_batch: list, thread_id: int, years: int = 5) -> list:
    """处理一批股票（在线程中运行）"""
    # 每个线程独立加载xtquant
    xtquant, xtdata = load_xtquant()
    
    current_year = datetime.now().year
    current_month = datetime.now().month
    start_year = current_year - years
    
    batch_results = []
    
    # 先批量下载所有股票的股价和财务数据
    print(f"  线程{thread_id}: 下载数据...")
    try:
        # 下载股价数据
        xtdata.download_history_data2(
            stock_list=stocks_batch,
            period='1d',
            start_time=f'{start_year}0101',
            end_time='20250317'
        )
        # 下载财务数据（不传时间参数）
        xtdata.download_financial_data2(
            stock_list=stocks_batch,
            table_list=['PershareIndex']
        )
    except Exception as e:
        print(f"  线程{thread_id}: 下载失败 - {e}")
    
    import time
    time.sleep(2)  # 等待下载完成
    
    for i, stock in enumerate(stocks_batch):
        try:
            # 1. 获取当前股价
            result = xtdata.get_market_data(
                stock_list=[stock],
                start_time="20250317",
                end_time="20250317",
                count=1
            )
            if not result or 'close' not in result:
                continue
            close_df = result['close']
            # 检查数据是否为空
            if close_df.empty or close_df.shape[1] == 0:
                continue
            try:
                current_price = float(close_df.iloc[0, 0])
            except:
                continue
            
            # 2. 获取财务数据
            fin_result = xtdata.get_financial_data(
                stock_list=[stock],
                table_list=['PershareIndex'],
                start_time=f'{start_year}0101',
                end_time=f'{current_year}1231',
                report_type='announce_time'
            )
            
            if not fin_result or stock not in fin_result:
                continue
            
            pershare = fin_result[stock].get('PershareIndex')
            if pershare is None or pershare.empty:
                continue
            
            # 3. 解析财务数据
            eps_dict = {}
            bps_dict = {}
            date_col = 'm_timetag' if 'm_timetag' in pershare.columns else 'endDate'
            
            for _, row in pershare.iterrows():
                end_date = row.get(date_col, '')
                if not end_date:
                    continue
                if isinstance(end_date, (int, float)):
                    try:
                        end_date = datetime.fromtimestamp(end_date / 1000).strftime('%Y%m%d')
                    except:
                        continue
                if not isinstance(end_date, str):
                    continue
                
                report_year = end_date[:4]
                eps = row.get('s_fa_eps_basic')
                bps = row.get('s_fa_bps')
                
                if eps and pd.notna(eps):
                    eps_dict[report_year] = eps
                if bps and pd.notna(bps):
                    bps_dict[report_year] = bps
            
            if not eps_dict:
                continue
            
            # 4. 计算当前PE/PB
            if current_month < 5:
                latest_report_year = current_year - 2
            else:
                latest_report_year = current_year - 1
            
            latest_year = None
            for y in sorted(eps_dict.keys(), reverse=True):
                if int(y) <= latest_report_year:
                    latest_year = y
                    break
            
            if not latest_year:
                continue
            
            latest_eps = eps_dict[latest_year]
            latest_bps = bps_dict.get(latest_year, None)
            
            if not latest_eps or latest_eps <= 0:
                continue
            
            current_pe = round(current_price / latest_eps, 2)
            current_pb = round(current_price / latest_bps, 2) if latest_bps and latest_bps > 0 else None
            
            # 5. 计算总市值
            try:
                info = xtdata.get_instrument_detail(stock)
                total_volume = info.get('TotalVolume', 0) if info else 0
                market_cap = round(current_price * total_volume / 1e8, 2) if total_volume else None
            except:
                market_cap = None
            
            batch_results.append({
                'stock': stock,
                'current_price': current_price,
                'latest_year': latest_year,
                'eps': latest_eps,
                'bps': latest_bps,
                'pe': current_pe,
                'pb': current_pb,
                'market_cap': market_cap
            })
            
            # 打印进度
            with _results_lock:
                print(f"  线程{thread_id}: {stock} 完成 ({len(_pe_pb_results) + i + 1})")
            
        except Exception as e:
            print(f"  线程{thread_id}: {stock} 失败 - {e}")
            continue
    
    return batch_results


def get_pe_pb_data_parallel(stock_list: list, years: int = 5, num_threads: int = 10) -> pd.DataFrame:
    """
    并行获取PE、PB数据
    
    Args:
        stock_list: 股票代码列表
        years: 获取近几年数据
        num_threads: 线程数
    
    Returns:
        DataFrame: 包含PE/PB、市值等
    """
    global _pe_pb_results
    _pe_pb_results = []
    
    total = len(stock_list)
    print(f"开始并行处理 {total} 只股票，使用 {num_threads} 个线程")
    print(f"每批约 {total // num_threads} 只股票")
    
    # 分批
    batch_size = max(1, total // num_threads)
    batches = []
    for i in range(0, total, batch_size):
        batches.append(stock_list[i:i + batch_size])
    
    start_time = time.time()
    
    # 使用线程池
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        futures = {
            executor.submit(process_stock_batch, batch, idx, years): idx 
            for idx, batch in enumerate(batches)
        }
        
        for future in as_completed(futures):
            try:
                batch_result = future.result()
                with _results_lock:
                    _pe_pb_results.extend(batch_result)
            except Exception as e:
                print(f"批次处理失败: {e}")
    
    elapsed = time.time() - start_time
    print(f"\n完成！共处理 {len(_pe_pb_results)} 只股票，耗时 {elapsed:.1f} 秒")
    
    return pd.DataFrame(_pe_pb_results)


def get_all_stocks():
    """获取沪深京A股全部股票"""
    xtquant, xtdata = load_xtquant()
    stocks = xtdata.get_stock_list_in_sector('沪深京A股')
    print(f"获取到 {len(stocks)} 只股票")
    return stocks


def main():
    """测试"""
    # 测试股票列表
    test_stocks = ['300140.SZ', '300003.SZ', '000001.SZ']

    print("="*60)
    print(" PE/PB估值分析")
    print("="*60)

    # 获取PE/PB数据
    df_pepb = get_pe_pb_data(test_stocks, years=5)
    
    if not df_pepb.empty:
        print("\n" + "="*60)
        print(" PE/PB分析结果:")
        print("="*60)
        print(df_pepb.to_string(index=False))
        
        # 导出CSV
        export_pe_pb_csv(df_pepb)

    # 同时导出基本面数据（含市值）
    print("\n" + "="*60)
    print(" 基本面数据（含市值）")
    print("="*60)
    df = get_financial_data(test_stocks, years=5)
    print_financial_report(df)
    export_to_csv(df)


if __name__ == '__main__':
    main()
