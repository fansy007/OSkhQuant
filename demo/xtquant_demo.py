# -*- coding: utf-8 -*-
"""
xtquant 数据获取示例
演示如何获取股票的分时数据和K线数据

运行方式: 在项目根目录运行
    python demo/xtquant_demo.py
"""

import sys
import os
import importlib
import importlib.util
from datetime import datetime, timedelta

# 项目根目录
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
xtquant_path = os.path.join(project_root, 'xtquant')


def load_xtquant():
    """手动加载本地xtquant包"""
    # 清除可能的缓存
    for key in list(sys.modules.keys()):
        if 'xtquant' in key:
            del sys.modules[key]

    # 1. 加载xtquant主模块
    spec = importlib.util.spec_from_file_location("xtquant", os.path.join(xtquant_path, "__init__.py"))
    xtquant = importlib.util.module_from_spec(spec)
    sys.modules['xtquant'] = xtquant
    spec.loader.exec_module(xtquant)

    # 2. 加载xtdata子模块
    xtdata_spec = importlib.util.spec_from_file_location("xtquant.xtdata", os.path.join(xtquant_path, "xtdata.py"))
    xtdata = importlib.util.module_from_spec(xtdata_spec)
    sys.modules['xtquant.xtdata'] = xtdata
    xtdata_spec.loader.exec_module(xtdata)

    return xtdata


# 手动加载xtquant
xtdata = load_xtquant()

# 导入pandas
try:
    import pandas as pd
except ImportError:
    print("错误: 需要安装pandas - pip install pandas")
    sys.exit(1)


def get_intraday_data(stock_code: str) -> 'pd.DataFrame':
    """
    获取股票当天分时数据（tick数据）
    """
    print(f"\n正在获取 {stock_code} 的当天分时数据...")

    now = datetime.now()
    end_time = now.strftime('%Y%m%d')
    start_time = (now - timedelta(days=5)).strftime('%Y%m%d')

    # 下载数据到本地
    try:
        xtdata.download_history_data(
            stock_code=stock_code,
            period='tick',
            start_time=start_time,
            end_time=end_time
        )
    except Exception as e:
        print(f"下载数据时出错: {e}")

    # 从本地读取数据
    # 注意: tick数据用 lastPrice 获取当前时刻的最新价，而不是 close
    data = xtdata.get_market_data_ex(
        field_list=['time', 'open', 'high', 'low', 'lastPrice', 'volume', 'amount'],
        stock_list=[stock_code],
        period='tick',
        start_time=start_time,
        end_time=end_time,
        count=-1,
        dividend_type='none',
        fill_data=True
    )

    if not data or stock_code not in data:
        print(f"未获取到 {stock_code} 的分时数据")
        return pd.DataFrame()

    df = data[stock_code].copy()
    df['time'] = pd.to_datetime(df['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)

    # 筛选今天的数据
    today = now.date()
    df['date'] = df['time'].dt.date
    df_today = df[df['date'] == today].copy()
    # 重命名 lastPrice 为 close，方便理解
    df_today = df_today.rename(columns={'lastPrice': 'close'})
    df_today = df_today[['time', 'open', 'high', 'low', 'close', 'volume', 'amount']]
    df_today = df_today.reset_index(drop=True)

    return df_today


def get_kline_data(stock_code: str, days: int = 30) -> 'pd.DataFrame':
    """
    获取股票K线数据（日线）
    """
    print(f"\n正在获取 {stock_code} 的{days}天K线数据...")

    now = datetime.now()
    end_time = now.strftime('%Y%m%d')
    start_time = (now - timedelta(days=days * 3)).strftime('%Y%m%d')

    # 下载数据到本地
    try:
        xtdata.download_history_data(
            stock_code=stock_code,
            period='1d',
            start_time=start_time,
            end_time=end_time
        )
    except Exception as e:
        print(f"下载数据时出错: {e}")

    # 从本地读取数据
    data = xtdata.get_market_data_ex(
        field_list=['time', 'open', 'high', 'low', 'close', 'volume'],
        stock_list=[stock_code],
        period='1d',
        start_time=start_time,
        end_time=end_time,
        count=-1,
        dividend_type='none',
        fill_data=True
    )

    if not data or stock_code not in data:
        print(f"未获取到 {stock_code} 的K线数据")
        return pd.DataFrame()

    df = data[stock_code].copy()
    df['time'] = pd.to_datetime(df['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)
    df = df.tail(days).copy()
    df['time'] = df['time'].dt.strftime('%Y-%m-%d')
    df = df.rename(columns={'time': 'date'})
    df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
    df = df.reset_index(drop=True)

    return df


def main():
    print("=" * 60)
    print(" xtquant 数据获取示例")
    print("=" * 60)

    stock_code = "000001.SZ"  # 平安银行

    # 1. 获取当天分时数据
    print("\n" + "-" * 40)
    print("【1】获取当天分时数据")
    print("-" * 40)
    intraday_df = get_intraday_data(stock_code)

    if not intraday_df.empty:
        print(f"\n成功获取 {len(intraday_df)} 条分时数据")
        print("\n前5条:")
        print(intraday_df.head().to_string(index=False))
        print("\n最后5条:")
        print(intraday_df.tail().to_string(index=False))
    else:
        print("分时数据为空")

    # 2. 获取30天K线数据
    print("\n" + "-" * 40)
    print("【2】获取30天K线数据")
    print("-" * 40)
    kline_df = get_kline_data(stock_code, days=30)

    if not kline_df.empty:
        print(f"\n成功获取 {len(kline_df)} 条K线数据")
        print("\n全部数据:")
        print(kline_df.to_string(index=False))
    else:
        print("K线数据为空")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
