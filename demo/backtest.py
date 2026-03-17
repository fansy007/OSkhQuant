# -*- coding: utf-8 -*-
"""
回测系统
使用选股系统进行选股，按回撤止损策略卖出

运行方式: python demo/backtest.py
"""
import sys
import os
import importlib
import importlib.util
from datetime import datetime, timedelta
import pandas as pd

# 项目根目录
PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'demo', 'screen_config.txt')

# 回测参数 (可运行时输入)
INITIAL_CAPITAL = 1000000  # 初始资金100万
STOP_LOSS_PCT = 0.12  # 止损回撤12%

# 回测时间段 (可运行时输入)
BACKTEST_START = '20240101'
BACKTEST_END = '20250601'


def get_user_inputs():
    """获取用户输入的回测参数，支持命令行参数"""
    global INITIAL_CAPITAL, BACKTEST_START, BACKTEST_END

    print("\n" + "=" * 50)
    print(" 回测参数设置")
    print("=" * 50)

    # 检查命令行参数: python backtest.py [初始资金] [开始日期] [结束日期]
    if len(sys.argv) > 1:
        try:
            INITIAL_CAPITAL = int(sys.argv[1])
            print(f"  初始资金: {INITIAL_CAPITAL:,} (命令行)")
        except:
            pass

        if len(sys.argv) > 2 and len(sys.argv[2]) == 8 and sys.argv[2].isdigit():
            BACKTEST_START = sys.argv[2]
            print(f"  开始日期: {BACKTEST_START} (命令行)")

        if len(sys.argv) > 3 and len(sys.argv[3]) == 8 and sys.argv[3].isdigit():
            BACKTEST_END = sys.argv[3]
            print(f"  结束日期: {BACKTEST_END} (命令行)")
    else:
        # 交互式输入
        capital_input = input(f"初始资金 (默认 {INITIAL_CAPITAL:,}): ").strip()
        if capital_input:
            try:
                INITIAL_CAPITAL = int(float(capital_input))
            except ValueError:
                print("  输入无效，使用默认值")

        start_input = input(f"开始日期 YYYYMMDD (默认 {BACKTEST_START}): ").strip()
        if start_input and len(start_input) == 8 and start_input.isdigit():
            BACKTEST_START = start_input

        end_input = input(f"结束日期 YYYYMMDD (默认 {BACKTEST_END}): ").strip()
        if end_input and len(end_input) == 8 and end_input.isdigit():
            BACKTEST_END = end_input

    print(f"\n当前设置:")
    print(f"  初始资金: {INITIAL_CAPITAL:,}")
    print(f"  回测期间: {BACKTEST_START} - {BACKTEST_END}")
    print(f"  止损回撤: {STOP_LOSS_PCT*100}%")


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
        'turnover': None,
        'net_profit': [],
        'cashflow': [],
    }

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

            elif cond_type in ('net_profit', 'cashflow'):
                quarter = parts[1].lower()
                op = parts[2]
                value = float(parts[3])

                if value > 10:
                    periods = 0
                else:
                    periods = int(value)

                item = (quarter, op, value if periods == 0 else periods, periods)
                config[cond_type].append(item)

    return config


# 季度配置
QUARTER_DATE = {'q1': '0331', 'q2': '0630', 'q3': '0930', 'q4': '1231'}
CURRENT_YEAR = 2025


def get_date_from_quarter(quarter: str, year: int) -> str:
    q_date = QUARTER_DATE.get(quarter.lower(), '1231')
    return f"{year}{q_date}"


def get_recent_dates(quarter: str, periods: int) -> list:
    q_map = {'q1': 1, 'q2': 2, 'q3': 3, 'q4': 4}
    q_num = q_map.get(quarter.lower(), 4)

    dates = []
    for i in range(periods):
        year = CURRENT_YEAR - i
        dates.append(get_date_from_quarter(quarter, year))

    return dates


def get_stocks_by_industry(xtdata, industry_name: str) -> list:
    """获取指定行业的所有股票"""
    stock_list = xtdata.get_stock_list_in_sector(industry_name)
    if not stock_list:
        print(f"  未找到行业: {industry_name}")
        return []
    print(f"  行业 '{industry_name}': {len(stock_list)} 只")
    return stock_list


def get_turnover_qualified(xtdata, stock_list: list, config: dict) -> list:
    """筛选换手率"""
    turnover_cfg = config.get('turnover')
    if not turnover_cfg:
        return stock_list

    days, pct_min, avg_min = turnover_cfg
    print(f"  换手率筛选 (最近{days}天, >{pct_min}%天数>0, 日均>{avg_min}%)...")

    kline_data = xtdata.get_market_data(
        field_list=['volume'],
        stock_list=stock_list,
        period='1d',
        count=days
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
    if volumes is None:
        return []

    for stock in stock_list:
        try:
            if stock not in volumes.index:
                continue

            stock_volumes = volumes.loc[stock].values
            float_vol = float_volumes.get(stock, 0)

            if float_vol and float_vol > 0:
                turnovers = [v * 100 / float_vol * 100 for v in stock_volumes]
                days_over = sum(1 for t in turnovers if t > pct_min)
                avg_turnover = sum(turnovers) / len(turnovers)

                if days_over > 0 and avg_turnover > avg_min:
                    qualified.append(stock)
        except:
            continue

    print(f"    换手率筛选后: {len(qualified)} 只")
    return qualified


def get_financial_qualified(xtdata, stock_list: list, config: dict) -> list:
    """筛选财务指标 - 使用最近可用数据"""
    net_profit_conds = config.get('net_profit', [])
    cashflow_conds = config.get('cashflow', [])

    if not net_profit_conds and not cashflow_conds:
        return stock_list

    print("  财务指标筛选...")

    # 尝试下载财务数据
    try:
        xtdata.download_financial_data2(
            stock_list=stock_list,
            table_list=['Income', 'CashFlow']
        )
    except Exception as e:
        print(f"    财务数据下载失败: {e}")

    qualified = []

    for stock in stock_list:
        try:
            # 获取财务数据
            income_data = xtdata.get_financial_data(
                stock_list=[stock],
                table_list=['Income'],
                start_time='20200101',
                end_time='20251231'
            )

            cashflow_data = xtdata.get_financial_data(
                stock_list=[stock],
                table_list=['CashFlow'],
                start_time='20200101',
                end_time='20251231'
            )

            income = income_data.get(stock, {}).get('Income', pd.DataFrame())
            cashflow = cashflow_data.get(stock, {}).get('CashFlow', pd.DataFrame())

            if income.empty:
                continue

            passed = True

            # 检查净利润条件
            for quarter, op, value, periods in net_profit_conds:
                if periods == 0:
                    # 静态条件
                    date = get_date_from_quarter(quarter, CURRENT_YEAR - 1)
                    if 'm_timetag' in income.columns:
                        row = income[income['m_timetag'].astype(str) == date]
                        if row.empty:
                            passed = False
                            break
                        val = row['net_profit_incl_min_int_inc'].iloc[0] if 'net_profit_incl_min_int_inc' in row.columns else None
                        if val is None or pd.isna(val):
                            passed = False
                            break
                        if op == '>' and not val > value:
                            passed = False
                            break
                else:
                    # 动态条件：连续N期
                    dates = get_recent_dates(quarter, periods)
                    values = []
                    if 'm_timetag' in income.columns:
                        for d in dates:
                            row = income[income['m_timetag'].astype(str) == d]
                            if row.empty:
                                values.append(None)
                            else:
                                val = row['net_profit_incl_min_int_inc'].iloc[0] if 'net_profit_incl_min_int_inc' in row.columns else None
                                values.append(val if val and not pd.isna(val) else None)

                    if None in values or len(values) != periods:
                        passed = False
                        break

                    for i in range(len(values) - 1):
                        if values[i] is None or values[i+1] is None:
                            passed = False
                            break
                        if op == '>' and not values[i] > values[i + 1]:
                            passed = False
                            break

            if not passed:
                continue

            # 检查现金流条件
            for quarter, op, value, periods in cashflow_conds:
                if periods == 0:
                    date = get_date_from_quarter(quarter, CURRENT_YEAR - 1)
                    if not cashflow.empty and 'm_timetag' in cashflow.columns:
                        row = cashflow[cashflow['m_timetag'].astype(str) == date]
                        if row.empty:
                            passed = False
                            break
                        val = row['net_cash_flows_oper_act'].iloc[0] if 'net_cash_flows_oper_act' in row.columns else None
                        if val is None or pd.isna(val):
                            passed = False
                            break
                        if op == '>' and not val > value:
                            passed = False
                            break
                else:
                    dates = get_recent_dates(quarter, periods)
                    values = []
                    if not cashflow.empty and 'm_timetag' in cashflow.columns:
                        for d in dates:
                            row = cashflow[cashflow['m_timetag'].astype(str) == d]
                            if row.empty:
                                values.append(None)
                            else:
                                val = row['net_cash_flows_oper_act'].iloc[0] if 'net_cash_flows_oper_act' in row.columns else None
                                values.append(val if val and not pd.isna(val) else None)

                    if None in values or len(values) != periods:
                        passed = False
                        break

                    for i in range(len(values) - 1):
                        if values[i] is None or values[i+1] is None:
                            passed = False
                            break
                        if op == '>' and not values[i] > values[i + 1]:
                            passed = False
                            break

            if passed:
                qualified.append(stock)

        except Exception as e:
            continue

    print(f"    财务筛选后: {len(qualified)} 只")
    return qualified


def run_stock_screener(xtdata, config: dict) -> list:
    """运行选股系统"""
    print("\n" + "=" * 50)
    print(" 选股系统")
    print("=" * 50)

    # 获取行业股票
    industry = config.get('industry')
    if not industry:
        print("未配置行业")
        return []

    stock_list = get_stocks_by_industry(xtdata, industry)
    if not stock_list:
        return []

    # 换手率筛选
    if config.get('turnover'):
        stock_list = get_turnover_qualified(xtdata, stock_list, config)
        if not stock_list:
            print("换手率筛选无股票")
            return []

    # 财务筛选
    stock_list = get_financial_qualified(xtdata, stock_list, config)

    print(f"\n选股结果: {len(stock_list)} 只")
    for s in stock_list:
        print(f"  - {s}")

    return stock_list


def get_trading_dates(xtdata, start_date: str, end_date: str) -> list:
    """获取交易日列表"""
    # 获取所有股票的历史数据来推断交易日
    # 简单方法：生成日期范围
    start = datetime.strptime(start_date, '%Y%m%d')
    end = datetime.strptime(end_date, '%Y%m%d')

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # 周一到周五
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)

    return dates


def get_stock_history(xtdata, stock_list: list, start_date: str, end_date: str) -> dict:
    """获取股票历史K线数据"""
    print(f"\n获取历史K线数据 ({start_date} - {end_date})...")

    # 先下载数据
    for stock in stock_list:
        try:
            xtdata.download_history_data(stock_code=stock, period='1d', start_time=start_date, end_time=end_date)
        except:
            pass

    # 使用get_market_data_ex获取数据
    kline_data = xtdata.get_market_data_ex(
        field_list=['time', 'open', 'high', 'low', 'close', 'volume'],
        stock_list=stock_list,
        period='1d',
        start_time=start_date,
        end_time=end_date,
        count=-1,
        dividend_type='none',
        fill_data=True
    )

    result = {}

    if not kline_data:
        print("  无K线数据")
        return result

    for stock in stock_list:
        try:
            if stock not in kline_data:
                print(f"  {stock} 无数据")
                continue

            df = kline_data[stock].copy()

            if df.empty:
                continue

            # 转换时间格式
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)
                df = df.sort_values('time')
                result[stock] = df
        except Exception as e:
            print(f"  {stock} 数据获取失败: {e}")
            continue

    print(f"  成功获取 {len(result)} 只股票的历史数据")
    return result


def run_backtest(xtdata, config: dict):
    """运行回测"""
    print("\n" + "=" * 60)
    print(" 回测系统")
    print("=" * 60)
    print(f"初始资金: {INITIAL_CAPITAL:,.0f} 元")
    print(f"止损线: 回撤 {STOP_LOSS_PCT*100}%")
    print(f"回测期间: {BACKTEST_START} - {BACKTEST_END}")

    # 运行选股
    selected_stocks = run_stock_screener(xtdata, config)
    if not selected_stocks:
        print("选股无结果")
        return

    # 获取历史数据
    # 使用更长时间获取足够数据
    hist_data = get_stock_history(xtdata, selected_stocks, '20230101', BACKTEST_END)

    if not hist_data:
        print("无法获取历史数据")
        return

    # 交易日期
    all_dates = set()
    for df in hist_data.values():
        all_dates.update(df['time'].dt.strftime('%Y%m%d').tolist())

    trading_dates = sorted([d for d in all_dates if BACKTEST_START <= d <= BACKTEST_END])

    if not trading_dates:
        print("无交易日期")
        return

    print(f"\n开始回测 ({len(trading_dates)} 个交易日)...")

    # 持仓: {stock: {'shares': 数量, 'cost': 成本价, 'peak_price': 最高价}}
    positions = {}
    cash = INITIAL_CAPITAL

    # 交易记录
    trades = []

    # 每日资产
    daily_assets = []

    # 每月调仓日 (简化为每20个交易日选一次)
    rebalance_interval = 20
    next_rebalance_idx = rebalance_interval

    for i, date_str in enumerate(trading_dates):
        date = datetime.strptime(date_str, '%Y%m%d')

        # 获取当日收盘价
        current_prices = {}
        for stock, df in hist_data.items():
            row = df[df['time'] == date]
            if not row.empty:
                current_prices[stock] = row['close'].iloc[0]

        # 检查持仓是否需要止损
        positions_to_close = []
        for stock, pos in list(positions.items()):
            if stock not in current_prices:
                continue

            current_price = current_prices[stock]

            # 更新最高价
            if current_price > pos['peak_price']:
                pos['peak_price'] = current_price

            # 检查是否触发止损
            if pos['peak_price'] > 0:
                drawdown = (pos['peak_price'] - current_price) / pos['peak_price']
                if drawdown >= STOP_LOSS_PCT:
                    positions_to_close.append(stock)
                    reason = '止损'
                    profit = (current_price - pos['cost']) * pos['shares']
                    trades.append({
                        'date': date_str,
                        'stock': stock,
                        'action': 'SELL',
                        'price': current_price,
                        'shares': pos['shares'],
                        'profit': profit,
                        'reason': reason
                    })
                    cash += current_price * pos['shares']

        # 卖出止损的股票
        for stock in positions_to_close:
            del positions[stock]

        # 定期重新选股和调仓
        if i >= next_rebalance_idx and cash > 0:
            print(f"\n{date_str} 调仓日 (剩余现金: {cash:,.0f})")

            # 重新选股
            new_stocks = run_stock_screener(xtdata, config)

            if new_stocks:
                # 计算可买资金
                available_cash = cash
                per_stock_cash = available_cash / len(new_stocks)

                # 买入新股
                for stock in new_stocks:
                    if stock in positions:
                        continue  # 已持有

                    if stock not in current_prices:
                        continue

                    price = current_prices[stock]
                    if price <= 0:
                        continue

                    # 按100股整数倍买入
                    shares = int(per_stock_cash / price / 100) * 100
                    if shares > 0:
                        cost = price * shares
                        if cost <= cash:
                            positions[stock] = {
                                'shares': shares,
                                'cost': price,
                                'peak_price': price
                            }
                            cash -= cost
                            trades.append({
                                'date': date_str,
                                'stock': stock,
                                'action': 'BUY',
                                'price': price,
                                'shares': shares,
                                'cost': cost,
                                'reason': '调仓'
                            })

            next_rebalance_idx = i + rebalance_interval

        # 计算当日总资产
        total_value = cash
        for stock, pos in positions.items():
            if stock in current_prices:
                total_value += current_prices[stock] * pos['shares']

        daily_assets.append({
            'date': date_str,
            'cash': cash,
            'stock_value': total_value - cash,
            'total_value': total_value,
            'positions': len(positions)
        })

        # 打印进度
        if (i + 1) % 50 == 0:
            print(f"  进度: {i+1}/{len(trading_dates)}, 资产: {total_value:,.0f}, 持仓: {len(positions)}")

    # 回测结束，强制平仓
    print("\n回测结束，平仓...")
    final_date = trading_dates[-1]
    final_prices = {}
    for stock, df in hist_data.items():
        row = df[df['time'] == datetime.strptime(final_date, '%Y%m%d')]
        if not row.empty:
            final_prices[stock] = row['close'].iloc[0]

    final_value = cash
    for stock, pos in list(positions.items()):
        if stock in final_prices:
            price = final_prices[stock]
            profit = (price - pos['cost']) * pos['shares']
            trades.append({
                'date': final_date,
                'stock': stock,
                'action': 'SELL',
                'price': price,
                'shares': pos['shares'],
                'profit': profit,
                'reason': '结束平仓'
            })
            final_value += price * pos['shares']

    positions.clear()

    # 输出结果
    print("\n" + "=" * 60)
    print(" 回测结果")
    print("=" * 60)

    total_return = (final_value - INITIAL_CAPITAL) / INITIAL_CAPITAL * 100
    print(f"初始资金: {INITIAL_CAPITAL:,.0f}")
    print(f"最终资产: {final_value:,.0f}")
    print(f"总收益: {final_value - INITIAL_CAPITAL:,.0f} ({total_return:.2f}%)")

    # 交易统计
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    sell_trades = [t for t in trades if t['action'] == 'SELL']
    win_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
    loss_trades = [t for t in sell_trades if t.get('profit', 0) <= 0]

    print(f"\n交易统计:")
    print(f"  买入次数: {len(buy_trades)}")
    print(f"  卖出次数: {len(sell_trades)}")
    if sell_trades:
        print(f"  盈利次数: {len(win_trades)}")
        print(f"  亏损次数: {len(loss_trades)}")
        win_rate = len(win_trades) / len(sell_trades) * 100
        print(f"  胜率: {win_rate:.1f}%")

        if win_trades:
            avg_win = sum(t['profit'] for t in win_trades) / len(win_trades)
            print(f"  平均盈利: {avg_win:,.0f}")
        if loss_trades:
            avg_loss = sum(t['profit'] for t in loss_trades) / len(loss_trades)
            print(f"  平均亏损: {avg_loss:,.0f}")

    # 保存交易记录
    trades_df = pd.DataFrame(trades)
    if not trades_df.empty:
        trades_df.to_csv('demo/backtest_trades.csv', index=False, encoding='utf-8-sig')
        print(f"\n交易记录已保存: demo/backtest_trades.csv")

    # 保存每日资产
    assets_df = pd.DataFrame(daily_assets)
    if not assets_df.empty:
        assets_df.to_csv('demo/backtest_assets.csv', index=False, encoding='utf-8-sig')
        print(f"每日资产已保存: demo/backtest_assets.csv")

    # 绘制资产曲线
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates

        plt.figure(figsize=(12, 6))
        assets_df['date'] = pd.to_datetime(assets_df['date'])
        plt.plot(assets_df['date'], assets_df['total_value'], 'b-', linewidth=1.5)
        plt.axhline(y=INITIAL_CAPITAL, color='gray', linestyle='--', alpha=0.5)
        plt.title('Backtest - Asset Curve', fontsize=14)
        plt.xlabel('Date')
        plt.ylabel('Total Value (CNY)')
        plt.grid(True, alpha=0.3)
        plt.gcf().autofmt_xdate()
        plt.tight_layout()
        plt.savefig('demo/backtest_curve.png', dpi=150)
        print(f"资产曲线已保存: demo/backtest_curve.png")
    except Exception as e:
        print(f"绘图失败: {e}")


def main():
    print("=" * 60)
    print(" 股票回测系统")
    print("=" * 60)

    # 获取用户输入
    get_user_inputs()

    # 加载配置
    config = load_config()
    print(f"\n选股配置:")
    print(f"  行业: {config['industry']}")
    print(f"  换手率: {config['turnover']}")
    print(f"  净利润: {config['net_profit']}")
    print(f"  现金流: {config['cashflow']}")

    # 加载xtquant
    print("\n加载xtquant...")
    xtquant, xtdata = load_xtquant()
    print("xtquant 加载成功")

    # 运行回测
    run_backtest(xtdata, config)


if __name__ == "__main__":
    main()
