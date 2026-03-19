# -*- coding: utf-8 -*-
"""
买入策略模块 - 基本面选股
根据配置文件中的条件进行选股买入

配置文件: strategy/buy_fundamental_strategy.config
"""
import sys
import os
import importlib
import importlib.util
from datetime import datetime, timedelta
import pandas as pd

# 项目根目录（demo_claw）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', 'xtquant')
CSV_PATH = os.path.join(PROJECT_ROOT, 'financial_data', 'financial_data.csv')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'strategy', 'buy_fundamental_strategy.config')

# 季度映射到日期
QUARTER_DATE = {
    'q1': '0331',
    'q2': '0630',
    'q3': '0930',
    'q4': '1231'
}

# 支持的财务字段列表
financial_fields = [
    # 利润表
    'revenue', 'oper_profit', 'net_profit_incl_min_int_inc',
    'net_profit_incl_min_int_inc_after', 'net_profit_excl_min_int_inc',
    # 现金流量表
    'net_cash_flows_oper_act', 'net_cash_flows_inv_act', 'net_cash_flows_fnc_act',
    # 每股指标
    'du_return_on_equity', 'inc_revenue_rate', 'adjusted_net_profit_rate',
    'gross_profit', 'net_profit_rate', 'gear_ratio'
]

# 各表字段映射
income_fields = [
    'revenue', 'oper_profit', 'net_profit_incl_min_int_inc',
    'net_profit_incl_min_int_inc_after', 'net_profit_excl_min_int_inc'
]
cashflow_fields = [
    'net_cash_flows_oper_act', 'net_cash_flows_inv_act', 'net_cash_flows_fnc_act'
]
pershare_fields = [
    'du_return_on_equity', 'inc_revenue_rate', 'adjusted_net_profit_rate',
    'gross_profit', 'net_profit_rate', 'gear_ratio'
]


def get_latest_q4_report(report_date: str) -> str:
    """根据回测日期，返回上一个已发布的Q4财报日期"""
    year = int(report_date[:4])
    month = int(report_date[4:6])
    day = int(report_date[6:8])

    if month > 4:
        return f'{year}1231'
    elif month == 4:
        if day >= 30:
            return f'{year}1231'
        else:
            return f'{year - 1}1231'
    else:
        return f'{year - 1}1231'


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


def load_config():
    """加载配置文件"""
    config = {
        'industry': None,
        'turnover': None,  # (days, pct_min, avg_min)
    }

    # 初始化静态和动态条件（使用全局financial_fields）
    for field in financial_fields:
        config[f's_{field}'] = []  # 静态条件
        config[f'd_{field}'] = []  # 动态条件

    if not os.path.exists(CONFIG_PATH):
        print(f"配置文件不存在: {CONFIG_PATH}")
        return config

    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = [p.strip() for p in line.split(',')]
            cond_type = parts[0]

            if cond_type == 'industry':
                config['industry'] = parts[1]

            elif cond_type == 'turnover':
                config['turnover'] = (int(parts[1]), float(parts[2]), float(parts[3]))

            elif cond_type.startswith('s_'):
                if cond_type in config:
                    op = parts[1]
                    value = float(parts[2])
                    config[cond_type].append((op, value))

            elif cond_type.startswith('d_'):
                if cond_type in config:
                    op = parts[1]
                    periods = int(parts[2])
                    config[cond_type].append((op, periods))

    return config


def get_stocks_by_industry(xtdata, industry_name: str) -> list:
    """获取指定行业的所有股票"""
    stock_list = xtdata.get_stock_list_in_sector(industry_name)
    if not stock_list:
        print(f"  未找到行业: {industry_name}")
        return []
    return stock_list


def load_financial_from_csv(stock_list: list) -> pd.DataFrame:
    """从CSV加载财务数据"""
    if not os.path.exists(CSV_PATH):
        return pd.DataFrame()

    df = pd.read_csv(CSV_PATH)
    df = df[df['stock_code'].isin(stock_list)]
    return df


def get_financial_from_xtquant(xtdata, stock_list: list) -> pd.DataFrame:
    """从xtquant获取财务数据并保存到CSV"""
    print("  从xtquant下载财务数据...")

    tables_needed = set()
    for f in financial_fields:
        if f in income_fields:
            tables_needed.add('Income')
        elif f in cashflow_fields:
            tables_needed.add('CashFlow')
        elif f in pershare_fields:
            tables_needed.add('PershareIndex')

    tables_to_download = list(tables_needed)
    if not tables_to_download:
        return pd.DataFrame()

    try:
        xtdata.download_financial_data2(
            stock_list=stock_list,
            table_list=tables_to_download
        )
    except Exception as e:
        print(f"  下载出错: {e}")
        return pd.DataFrame()

    all_data = xtdata.get_financial_data(
        stock_list=stock_list,
        table_list=tables_to_download,
        start_time='20200101',
        end_time='20251231'
    )

    records_dict = {}

    for stock in stock_list:
        for table in tables_to_download:
            table_data = all_data.get(stock, {}).get(table, pd.DataFrame())
            if table_data.empty or 'm_timetag' not in table_data.columns:
                continue

            for _, row in table_data.iterrows():
                date = str(row.get('m_timetag', ''))
                key = (stock, date)

                if key not in records_dict:
                    records_dict[key] = {'stock_code': stock, 'end_date': date}

                for field in financial_fields:
                    if field not in records_dict[key] or records_dict[key][field] is None:
                        records_dict[key][field] = row.get(field, None)

    all_records = list(records_dict.values())

    if all_records:
        new_df = pd.DataFrame(all_records)

        if os.path.exists(CSV_PATH):
            existing_df = pd.read_csv(CSV_PATH)
            combined_df = pd.concat([existing_df, new_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['stock_code', 'end_date'], keep='last')
            combined_df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
        else:
            new_df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')

        print(f"  已保存 {len(new_df)} 条新记录到CSV")
        return new_df

    return pd.DataFrame()


def check_turnover_metrics(stock_list: list, config: dict, xtdata, report_date: str) -> list:
    """筛选换手率"""
    turnover_cfg = config.get('turnover')
    if not turnover_cfg:
        return stock_list

    days, pct_min, avg_min = turnover_cfg

    # 计算起始日期
    start_year = int(report_date[:4])
    start_month = int(report_date[4:6])
    start_day = int(report_date[6:8])
    import datetime
    report_dt = datetime.datetime(start_year, start_month, start_day)
    start_dt = report_dt - datetime.timedelta(days=days + 30)
    start_time = start_dt.strftime('%Y%m%d')

    xtdata.download_history_data2(
        stock_list=stock_list,
        period='1d',
        start_time=start_time,
        end_time=report_date
    )

    kline_data = xtdata.get_market_data(
        field_list=['volume'],
        stock_list=stock_list,
        period='1d',
        start_time=start_time,
        end_time=report_date
    )

    float_volumes = {}
    for stock in stock_list:
        try:
            detail = xtdata.get_instrument_detail(stock)
            if detail:
                float_volumes[stock] = detail.get('FloatVolume', 0)
        except:
            float_volumes[stock] = 0

    qualified = []
    volumes = kline_data.get('volume')

    for stock in stock_list:
        try:
            if stock not in volumes.index:
                continue

            stock_volumes = volumes.loc[stock].values
            stock_volumes = stock_volumes[-days:] if len(stock_volumes) >= days else stock_volumes
            float_vol = float_volumes.get(stock, 0)

            if float_vol and float_vol > 0:
                turnovers = [v * 100 / float_vol * 100 for v in stock_volumes]
                days_over = sum(1 for t in turnovers if t > pct_min)
                avg_turnover = sum(turnovers) / len(turnovers)

                if days_over > 0 and avg_turnover > avg_min:
                    qualified.append(stock)
        except:
            continue

    return qualified


def get_q4_data(df: pd.DataFrame, field: str, report_date: str) -> float:
    """获取Q4数据：根据回测日期，取上一个已发布的Q4财报"""
    df = df.copy()
    df['end_date'] = df['end_date'].astype(str)

    q4_year = int(get_latest_q4_report(report_date)[:4])

    for i in range(5):
        year_to_check = q4_year - i
        q4_data = df[df['end_date'] == f'{year_to_check}1231']
        if not q4_data.empty and field in q4_data.columns:
            val = q4_data[field].iloc[-1]
            if val is not None and not pd.isna(val):
                return val

    return None


def get_latest_report_date(report_date: str) -> str:
    """根据回测日期，返回最新已发布的财报日期"""
    year = int(report_date[:4])
    month = int(report_date[4:6])

    if month >= 11:
        return f'{year}0930'
    elif month >= 8:
        return f'{year}0630'
    elif month >= 5:
        return f'{year}0331'
    elif month >= 4 and int(report_date[6:8]) >= 30:
        return f'{year - 1}1231'
    elif month >= 4:
        return f'{year - 1}1231'
    else:
        return f'{year - 1}0930'


def check_static_condition(df: pd.DataFrame, field: str, op: str, value: float, report_date: str) -> bool:
    """静态条件：Q4数据与固定值比较"""
    val = get_q4_data(df, field, report_date)
    if val is None:
        return False

    if op == '>':
        return val > value
    elif op == '<':
        return val < value
    elif op == '>=':
        return val >= value
    elif op == '<=':
        return val <= value
    elif op == '=':
        return val == value
    return False


def check_dynamic_condition(df: pd.DataFrame, field: str, op: str, periods: int, report_date: str) -> bool:
    """动态条件：连续N期增长"""
    df = df.copy()
    df['end_date'] = df['end_date'].astype(str)

    latest_report = get_latest_report_date(report_date)
    latest_q = latest_report[4:]

    same_quarter_df = df[df['end_date'].str.endswith(latest_q)]

    if same_quarter_df.empty:
        return False

    same_quarter_df = same_quarter_df.sort_values('end_date', ascending=False)
    values = same_quarter_df[field].tolist()

    valid_values = []
    for v in values:
        if v is not None and not pd.isna(v):
            valid_values.append(v)

    if len(valid_values) < periods + 1:
        return False

    for i in range(periods):
        current_val = valid_values[i]
        prev_val = valid_values[i + 1]

        if op == '>':
            if not current_val > prev_val:
                return False
        elif op == '<':
            if not current_val < prev_val:
                return False
        elif op == '>=':
            if not current_val >= prev_val:
                return False

    return True


def check_financial_metrics(stock_list: list, financial_df: pd.DataFrame, config: dict, xtdata, report_date: str) -> list:
    """筛选财务指标"""
    # 收集配置中所有需要的字段
    fields_needed = []
    for key, value in config.items():
        if key.startswith('s_') and value:
            fields_needed.append(key[2:])
        elif key.startswith('d_') and value:
            fields_needed.append(key[2:])

    if not fields_needed:
        return stock_list

    # 从CSV加载
    financial_df = load_financial_from_csv(stock_list)

    stocks_with_data = set(financial_df['stock_code'].unique()) if not financial_df.empty else set()
    stocks_need_download = [s for s in stock_list if s not in stocks_with_data]

    if stocks_need_download and xtdata:
        new_df = get_financial_from_xtquant(xtdata, stocks_need_download)
        if not new_df.empty:
            combined_df = pd.concat([financial_df, new_df], ignore_index=True)
            combined_df = combined_df.drop_duplicates(subset=['stock_code', 'end_date'], keep='last')
            combined_df.to_csv(CSV_PATH, index=False, encoding='utf-8-sig')
            financial_df = combined_df

    if financial_df.empty:
        return []

    # 收集所有配置的条件
    static_conds = []
    dynamic_conds = []

    for key, value in config.items():
        if key.startswith('s_') and value:
            field = key[2:]
            for op, val in value:
                static_conds.append((field, op, val))
        elif key.startswith('d_') and value:
            field = key[2:]
            for op, periods in value:
                dynamic_conds.append((field, op, periods))

    qualified = []

    for stock in stock_list:
        df = financial_df[financial_df['stock_code'] == stock]
        if df.empty:
            continue

        try:
            passed = True

            for field, op, value in static_conds:
                if not check_static_condition(df, field, op, value, report_date):
                    passed = False
                    break

            if not passed:
                continue

            for field, op, periods in dynamic_conds:
                if not check_dynamic_condition(df, field, op, periods, report_date):
                    passed = False
                    break

            if passed:
                qualified.append(stock)

        except Exception as e:
            continue

    return qualified


# 全局变量
_xtdata = None


def stock_buy(report_date: str, xtdata=None) -> dict:
    """股票买入主函数

    Args:
        report_date: 回测日期，格式如 '20250615'
        xtdata: xtquant数据对象（可选）

    Returns:
        {
            'stocks': ['300xxx.SZ', ...],  # 选出的股票
            'date': '20250615',             # 选股日期
            'prices': {'300xxx.SZ': 10.5, ...},  # 当日收盘价
            'config': config                # 配置信息
        }
    """
    global _xtdata

    if xtdata is not None:
        _xtdata = xtdata
    else:
        if _xtdata is None:
            xtquant, _xtdata = load_xtquant()

    # 加载配置
    config = load_config()

    # 1. 获取行业股票
    if not config['industry']:
        return {'stocks': [], 'date': report_date, 'prices': {}, 'config': config}

    stock_list = get_stocks_by_industry(_xtdata, config['industry'])
    if not stock_list:
        return {'stocks': [], 'date': report_date, 'prices': {}, 'config': config}

    # 2. 技术指标筛选
    if config['turnover']:
        stock_list = check_turnover_metrics(stock_list, config, _xtdata, report_date)
        if not stock_list:
            return {'stocks': [], 'date': report_date, 'prices': {}, 'config': config}

    # 3. 财务指标筛选
    financial_df = load_financial_from_csv(stock_list)
    stock_list = check_financial_metrics(stock_list, financial_df, config, _xtdata, report_date)

    # 4. 获取当日收盘价
    prices = {}
    if stock_list:
        # 下载并获取当日K线数据
        import datetime
        start_year = int(report_date[:4])
        start_month = int(report_date[4:6])
        start_day = int(report_date[6:8])
        report_dt = datetime.datetime(start_year, start_month, start_day)
        start_dt = report_dt - datetime.timedelta(days=30)
        start_time = start_dt.strftime('%Y%m%d')

        try:
            _xtdata.download_history_data2(
                stock_list=stock_list,
                period='1d',
                start_time=start_time,
                end_time=report_date
            )

            kline_data = _xtdata.get_market_data(
                field_list=['close'],
                stock_list=stock_list,
                period='1d',
                start_time=start_time,
                end_time=report_date
            )

            close_data = kline_data.get('close')
            if close_data is not None:
                for stock in stock_list:
                    if stock in close_data.index:
                        prices[stock] = close_data.loc[stock].iloc[-1]
        except Exception as e:
            print(f"  获取收盘价失败: {e}")

    return {
        'stocks': stock_list,
        'date': report_date,
        'prices': prices,
        'config': config
    }


def main():
    """测试"""
    result = stock_buy('20250317')
    print(f"\n选股结果: {result['stocks']}")
    print(f"当日价格: {result['prices']}")


if __name__ == '__main__':
    main()
