# -*- coding: utf-8 -*-
"""
回测系统
调用买入模块和卖出模块进行回测
"""
import sys
import os
import importlib
import importlib.util
from datetime import datetime, timedelta
import pandas as pd

# 项目根目录（demo_claw）
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', 'xtquant')

# 输出路径
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'output')

# 配置文件路径
BACKTEST_CONFIG_PATH = os.path.join(PROJECT_ROOT, 'backtest.config')


def load_backtest_config():
    """加载回测配置文件"""
    config = {
        'initial_capital': 1000000,
        'start_date': '20240101',
        'end_date': '20250601',
        'min_buy_amount': 50000,
        'benchmark': '399006.SZ',
        'buy_strategy': 'buy_fundamental_strategy',
        'sell_strategy': 'sell_fundamental_strategy'
    }

    if not os.path.exists(BACKTEST_CONFIG_PATH):
        print(f"配置文件不存在: {BACKTEST_CONFIG_PATH}")
        return config

    with open(BACKTEST_CONFIG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = [p.strip() for p in line.split(',')]
            if len(parts) < 2:
                continue

            key = parts[0]
            value = parts[1]

            if key == 'initial_capital':
                config['initial_capital'] = int(value)
            elif key == 'start_date':
                config['start_date'] = value
            elif key == 'end_date':
                config['end_date'] = value
            elif key == 'min_buy_amount':
                config['min_buy_amount'] = int(value)
            elif key == 'benchmark':
                config['benchmark'] = value
            elif key == 'buy_strategy':
                config['buy_strategy'] = value
            elif key == 'sell_strategy':
                config['sell_strategy'] = value

    return config


def load_strategy(buy_strategy_name: str, sell_strategy_name: str):
    """动态加载策略模块"""
    strategy_path = os.path.join(PROJECT_ROOT, 'strategy')

    # 加载买入策略
    buy_module_path = os.path.join(strategy_path, f'{buy_strategy_name}.py')
    if not os.path.exists(buy_module_path):
        raise FileNotFoundError(f"买入策略文件不存在: {buy_module_path}")

    spec = importlib.util.spec_from_file_location('buy_strategy', buy_module_path)
    buy_module = importlib.util.module_from_spec(spec)
    sys.modules['buy_strategy'] = buy_module
    spec.loader.exec_module(buy_module)

    # 加载卖出策略
    sell_module_path = os.path.join(strategy_path, f'{sell_strategy_name}.py')
    if not os.path.exists(sell_module_path):
        raise FileNotFoundError(f"卖出策略文件不存在: {sell_module_path}")

    spec = importlib.util.spec_from_file_location('sell_strategy', sell_module_path)
    sell_module = importlib.util.module_from_spec(spec)
    sys.modules['sell_strategy'] = sell_module
    spec.loader.exec_module(sell_module)

    return buy_module, sell_module


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


def get_trading_dates(start_date: str, end_date: str, xtdata=None) -> list:
    """Get real trading dates (filter holidays)"""
    # 回退：使用工作日过滤
    start = datetime.strptime(start_date, '%Y%m%d')
    end = datetime.strptime(end_date, '%Y%m%d')

    dates = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            dates.append(current.strftime('%Y%m%d'))
        current += timedelta(days=1)

    return dates


def get_stock_prices(xtdata, stock_list: list, dates: list) -> dict:
    """批量获取股票历史价格（从本地读取，已在buy中预下载）"""
    if not stock_list or not dates:
        return {}

    start_date = dates[0]
    end_date = dates[-1]

    # 直接从本地读取（已在buy中批量预下载）
    try:
        kline_data = xtdata.get_market_data_ex(
            field_list=['time', 'open', 'high', 'low', 'close'],
            stock_list=stock_list,
            period='1d',
            start_time=start_date,
            end_time=end_date,
            count=-1,
            dividend_type='none',
            fill_data=True
        )

        result = {}
        for stock, df in kline_data.items():
            if df is None or df.empty:
                continue

            df = df.copy()
            if 'time' in df.columns:
                df['time'] = pd.to_datetime(df['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)
                df['date'] = df['time'].dt.strftime('%Y%m%d')
                result[stock] = df.set_index('date')['close'].to_dict()

        return result
    except Exception as e:
        print(f"获取价格失败: {e}")
        return {}


def get_benchmark_prices(xtdata, benchmark: str, dates: list) -> dict:
    """获取基准指数价格"""
    if not dates:
        return {}

    start_date = dates[0]
    end_date = dates[-1]

    # 下载数据
    try:
        xtdata.download_history_data2(
            stock_list=[benchmark],
            period='1d',
            start_time=start_date,
            end_time=end_date
        )
    except:
        pass

    # 读取数据
    try:
        kline_data = xtdata.get_market_data_ex(
            field_list=['time', 'close'],
            stock_list=[benchmark],
            period='1d',
            start_time=start_date,
            end_time=end_date,
            count=-1,
            dividend_type='none',
            fill_data=True
        )

        if benchmark in kline_data:
            df = kline_data[benchmark].copy()
            df['time'] = pd.to_datetime(df['time'].astype(float), unit='ms') + pd.Timedelta(hours=8)
            df['date'] = df['time'].dt.strftime('%Y%m%d')
            return df.set_index('date')['close'].to_dict()

        return {}
    except Exception as e:
        print(f"获取基准数据失败: {e}")
        return {}


class Backtest:
    """回测类"""

    def __init__(self, initial_capital: int = None,
                 start_date: str = None,
                 end_date: str = None):
        """初始化

        Args:
            initial_capital: 初始资金（可选，从配置读取）
            start_date: 开始日期（可选，从配置读取）
            end_date: 结束日期（可选，从配置读取）
        """
        # 加载回测配置
        self.backtest_config = load_backtest_config()

        # 参数优先使用传入值，否则使用配置值
        self.initial_capital = initial_capital if initial_capital else self.backtest_config['initial_capital']
        self.start_date = start_date if start_date else self.backtest_config['start_date']
        self.end_date = end_date if end_date else self.backtest_config['end_date']

        # 从回测配置读取的参数
        self.min_buy_amount = self.backtest_config['min_buy_amount']
        self.benchmark = self.backtest_config['benchmark']

        # 动态加载策略模块
        buy_strategy = self.backtest_config['buy_strategy']
        sell_strategy = self.backtest_config['sell_strategy']
        self.stock_buy, self.stock_sell = load_strategy(buy_strategy, sell_strategy)

        # 策略配置
        self.buy_config = self.stock_buy.load_config()
        self.sell_config = self.stock_sell.load_config()

        # 状态
        self.cash = self.initial_capital
        self.positions = {}  # {stock: {'shares': xxx, 'cost': xxx, 'buy_date': xxx, 'peak_price': xxx}}
        self.trades = []  # 交易记录
        self.daily_assets = []  # 每日资产

        # 基准
        self.benchmark_prices = {}

    def run(self):
        """运行回测"""
        print("=" * 60)
        print(f" 回测系统")
        print("=" * 60)
        print(f"初始资金: {self.initial_capital:,}")
        print(f"回测期间: {self.start_date} - {self.end_date}")
        print(f"买入门槛: {self.min_buy_amount}")
        print(f"止损: {self.sell_config.get('stop_loss', 0)}%")
        print(f"止盈: {self.sell_config.get('take_profit', 0)}%")
        print(f"再平衡: {self.sell_config.get('rebalance_days', 0)}天")
        print(f"基准: {self.benchmark}")
        print(f"买入策略: {self.backtest_config['buy_strategy']}")
        print(f"卖出策略: {self.backtest_config['sell_strategy']}")

        # 加载xtquant
        xtquant, xtdata = load_xtquant()
        self.xtdata = xtdata
        print("\nxtquant 加载成功")

        # 获取真实交易日（过滤节假日）
        trading_dates = get_trading_dates(self.start_date, self.end_date, xtdata)
        print(f"交易日: {len(trading_dates)} 天")

        # 预加载基准数据
        print("\n加载基准数据...")
        self.benchmark_prices = get_benchmark_prices(xtdata, self.benchmark, trading_dates)

        # 每日循环
        last_total_value = self.initial_capital
        last_benchmark_value = self.initial_capital

        for i, date_str in enumerate(trading_dates):
            # 打印进度
            print(f"  进度: {i+1}/{len(trading_dates)} | 日期: {date_str}")

            # 计算是否是调仓日
            day_num = i + 1  # 第几个交易日
            rebalance_days = self.sell_config.get('rebalance_days', 0)
            is_rebalance_day = (rebalance_days > 0 and day_num % rebalance_days == 0)

            # 获取当日价格（持仓股票需要更新价格）
            all_stocks_for_price = list(self.positions.keys())
            prices_data = get_stock_prices(xtdata, all_stocks_for_price, [date_str])
            today_prices = {}
            for stock, prices in prices_data.items():
                if date_str in prices:
                    today_prices[stock] = prices[date_str]

            # ========== 非调仓日：只检查止损止盈，不选股 ==========
            if not is_rebalance_day:
                # 检查止损止盈
                if self.positions:
                    to_sell = self.stock_sell.stock_sell(
                        self.positions, date_str, [], today_prices, is_rebalance_day=False
                    )
                    for stock, reason, price, shares, profit in to_sell:
                        if stock in self.positions:
                            if price is None or price != price:  # 跳过价格为NaN的情况
                                print(f"  跳过卖出 {stock}，价格无效")
                                continue
                            del self.positions[stock]
                            self.cash += price * shares
                            self.trades.append({
                                'date': date_str, 'stock': stock, 'action': 'SELL',
                                'price': price, 'shares': shares, 'profit': profit, 'reason': reason
                            })
                
                # 更新持仓最高价
                for stock, pos in self.positions.items():
                    if stock in today_prices:
                        if today_prices[stock] > pos['peak_price']:
                            pos['peak_price'] = today_prices[stock]

                # 记录当日资产
                stock_value = 0
                for stock, pos in self.positions.items():
                    if stock in today_prices and today_prices[stock] > 0:
                        stock_value += today_prices[stock] * pos['shares']
                    else:
                        stock_value += pos['cost'] * pos['shares']

                total_value = self.cash + stock_value
                
                # 非调仓日也要记录基准值
                if date_str in self.benchmark_prices and self.benchmark_prices[date_str]:
                    first_price = list(self.benchmark_prices.values())[0]
                    current_price = self.benchmark_prices[date_str]
                    last_benchmark_value = current_price / first_price * self.initial_capital
                
                self.daily_assets.append({
                    'date': date_str,
                    'cash': self.cash,
                    'stock_value': stock_value,
                    'total_value': total_value,
                    'positions': len(self.positions),
                    'benchmark_value': last_benchmark_value
                })
                continue

            # ========== 调仓日：选股 + 卖出 + 买入 ==========
            
            # 获取选股结果
            buy_result = self.stock_buy.stock_buy(date_str, xtdata)
            selected_stocks = buy_result.get('stocks', [])

            # 获取当日价格（包含持仓股票 + 选出的股票）
            all_stocks_for_price = list(set(selected_stocks + list(self.positions.keys())))
            prices_data = get_stock_prices(xtdata, all_stocks_for_price, [date_str])
            # 转换为 {stock: price} 格式
            today_prices = {}
            for stock, prices in prices_data.items():
                if date_str in prices:
                    today_prices[stock] = prices[date_str]

            # ========== 卖出（止损止盈 + 调仓） ==========
            if self.positions:
                if is_rebalance_day and day_num > 1:
                    # rebalance_day：调仓卖出（包含止损止盈）
                    to_sell = self.stock_sell.stock_sell(
                        self.positions, date_str, selected_stocks, today_prices, is_rebalance_day=True
                    )
                else:
                    # 非rebalance_day：只执行止损止盈
                    to_sell = self.stock_sell.stock_sell(
                        self.positions, date_str, [], today_prices, is_rebalance_day=False
                    )
                for stock, reason, price, shares, profit in to_sell:
                    if stock in self.positions:
                        if price is None or price != price:  # 跳过价格为NaN的情况
                            print(f"  跳过卖出 {stock}，价格无效")
                            continue
                        del self.positions[stock]
                        self.cash += price * shares
                        self.trades.append({
                            'date': date_str, 'stock': stock, 'action': 'SELL',
                            'price': price, 'shares': shares, 'profit': profit, 'reason': reason
                        })

            # ========== 买入（每天有钱就买，复用选股结果） ==========
            if self.cash >= self.min_buy_amount:
                if selected_stocks:
                    available_cash = self.cash
                    per_stock_cash = available_cash / len(selected_stocks)
                    for stock in selected_stocks:
                        if stock in self.positions:
                            continue
                        if stock not in today_prices:
                            continue
                        price = today_prices[stock]
                        if price <= 0 or price != price:
                            continue
                        shares = int(per_stock_cash / price / 100) * 100
                        if shares > 0:
                            cost = price * shares
                            if cost <= self.cash:
                                self.positions[stock] = {
                                    'shares': shares, 'cost': price,
                                    'buy_date': date_str, 'peak_price': price
                                }
                                self.cash -= cost
                                buy_reason = 'Initial Buy' if day_num == 1 else 'Daily Buy'
                                self.trades.append({
                                    'date': date_str, 'stock': stock, 'action': 'BUY',
                                    'price': price, 'shares': shares, 'cost': cost, 'reason': buy_reason
                                })

            # 更新持仓最高价
            for stock, pos in self.positions.items():
                if stock in today_prices:
                    if today_prices[stock] > pos['peak_price']:
                        pos['peak_price'] = today_prices[stock]

            # 记录当日资产
            stock_value = 0
            for stock, pos in self.positions.items():
                if stock in today_prices and today_prices[stock] > 0:
                                   stock_value += today_prices[stock] * pos['shares']
                else:
                    # 节假日没有价格，用成本价估算
                    stock_value += pos['cost'] * pos['shares']

            total_value = self.cash + stock_value

            # 基准收益
            benchmark_value = None
            if self.benchmark_prices:
                first_price = list(self.benchmark_prices.values())[0]
                if date_str in self.benchmark_prices and self.benchmark_prices[date_str]:
                    current_price = self.benchmark_prices[date_str]
                    benchmark_value = current_price / first_price * self.initial_capital
                    last_benchmark_value = benchmark_value
                else:
                    # 节假日没有数据，用上一个交易日
                    benchmark_value = last_benchmark_value

            # 如果当日没有交易（节假日），保持上一个交易日的数据
            if not today_prices or (total_value == self.cash and not today_prices):
                total_value = last_total_value

            last_total_value = total_value

            self.daily_assets.append({
                'date': date_str,
                'cash': self.cash,
                'stock_value': stock_value,
                'total_value': total_value,
                'positions': len(self.positions),
                'benchmark_value': benchmark_value if benchmark_value else last_benchmark_value
            })

            # 进度（每天打印已在上方）

        # 回测结束
        final_value = self.daily_assets[-1]['total_value'] if self.daily_assets else self.initial_capital

        # 平仓记录
        final_date = trading_dates[-1]
        for stock, pos in list(self.positions.items()):
            self.trades.append({
                'date': final_date,
                'stock': stock,
                'action': 'SELL',
                'price': pos['cost'],
                'shares': pos['shares'],
                'profit': 0,
                'reason': '结束平仓'
            })
        self.positions.clear()

        # 输出报告
        self.report(final_value)

    def report(self, final_value: float):
        """输出报告"""
        print("\n" + "=" * 60)
        print(" 回测结果")
        print("=" * 60)

        total_return = (final_value - self.initial_capital) / self.initial_capital * 100
        print(f"初始资金: {self.initial_capital:,}")
        print(f"最终资产: {final_value:,.0f}")
        print(f"总收益: {final_value - self.initial_capital:,.0f} ({total_return:.2f}%)")

        # 交易统计
        buy_trades = [t for t in self.trades if t['action'] == 'BUY']
        sell_trades = [t for t in self.trades if t['action'] == 'SELL']
        win_trades = [t for t in sell_trades if t.get('profit', 0) > 0]
        loss_trades = [t for t in sell_trades if t.get('profit', 0) <= 0]

        print(f"\n交易统计:")
        print(f"  买入次数: {len(buy_trades)}")
        print(f"  卖出次数: {len(sell_trades)}")
        if sell_trades:
            win_rate = len(win_trades) / len(sell_trades) * 100
            print(f"  盈利次数: {len(win_trades)}")
            print(f"  亏损次数: {len(loss_trades)}")
            print(f"  胜率: {win_rate:.1f}%")
            
            # 盈亏统计
            total_profit = sum([t.get('profit', 0) for t in sell_trades])
            total_win = sum([t.get('profit', 0) for t in win_trades])
            total_loss = sum([t.get('profit', 0) for t in loss_trades])
            avg_win = total_win / len(win_trades) if win_trades else 0
            avg_loss = total_loss / len(loss_trades) if loss_trades else 0
            profit_loss_ratio = abs(avg_win / avg_loss) if avg_loss != 0 else 0
            
            print(f"  盈亏总额: {total_profit:,.0f}")
            print(f"  盈利总额: {total_win:,.0f}")
            print(f"  亏损总额: {total_loss:,.0f}")
            print(f"  平均盈利: {avg_win:,.0f}")
            print(f"  平均亏损: {avg_loss:,.0f}")
            print(f"  盈亏比: {profit_loss_ratio:.2f}")
            
            # TOP5盈利
            if win_trades:
                print(f"\n  TOP5盈利:")
                sorted_wins = sorted(win_trades, key=lambda x: x.get('profit', 0), reverse=True)[:5]
                for t in sorted_wins:
                    print(f"    {t['stock']} | {t['date']} | +{t.get('profit', 0):,.0f}")
            
            # TOP5亏损
            if loss_trades:
                print(f"\n  TOP5亏损:")
                sorted_losses = sorted(loss_trades, key=lambda x: x.get('profit', 0))[:5]
                for t in sorted_losses:
                    print(f"    {t['stock']} | {t['date']} | {t.get('profit', 0):,.0f}")

        # 基准对比
        if self.daily_assets and self.benchmark_prices:
            first_asset = self.daily_assets[0]
            last_asset = self.daily_assets[-1]
            if first_asset['benchmark_value'] and last_asset['benchmark_value']:
                benchmark_return = (last_asset['benchmark_value'] - first_asset['benchmark_value']) / first_asset['benchmark_value'] * 100
                print(f"\n基准对比 ({self.benchmark}):")
                print(f"  基准收益: {benchmark_return:.2f}%")
                print(f"  超额收益: {total_return - benchmark_return:.2f}%")

        # 确保输出目录存在
        os.makedirs(OUTPUT_DIR, exist_ok=True)

        # 保存数据
        trades_df = pd.DataFrame(self.trades)
        if not trades_df.empty:
            trades_df.to_csv(os.path.join(OUTPUT_DIR, 'backtest_trades.csv'), index=False, encoding='utf-8-sig')
            print(f"\n交易记录已保存")

        assets_df = pd.DataFrame(self.daily_assets)
        if not assets_df.empty:
            assets_df.to_csv(os.path.join(OUTPUT_DIR, 'backtest_assets.csv'), index=False, encoding='utf-8-sig')
            print(f"每日资产已保存")

        # 可视化
        self.plot(assets_df)

    def plot(self, assets_df: pd.DataFrame):
        """绘制资产曲线"""
        try:
            import matplotlib.pyplot as plt
            import matplotlib.dates as mdates

            plt.figure(figsize=(12, 6))

            assets_df['date'] = pd.to_datetime(assets_df['date'])

            # 策略资产曲线
            plt.plot(assets_df['date'], assets_df['total_value'], 'b-', linewidth=1.5, label='Strategy')

            # 基准曲线
            if 'benchmark_value' in assets_df.columns:
                benchmark_df = assets_df[assets_df['benchmark_value'].notna()]
                if not benchmark_df.empty:
                    plt.plot(benchmark_df['date'], benchmark_df['benchmark_value'], 'r--', linewidth=1.5, label=self.benchmark)

            plt.axhline(y=self.initial_capital, color='gray', linestyle='--', alpha=0.5, label='Initial')

            plt.title('Backtest - Asset Curve', fontsize=14)
            plt.xlabel('Date')
            plt.ylabel('Value (CNY)')
            plt.legend()
            plt.grid(True, alpha=0.3)
            plt.gcf().autofmt_xdate()
            plt.tight_layout()
            plt.savefig(os.path.join(OUTPUT_DIR, 'backtest_curve.png'), dpi=150)
            print(f"资产曲线已保存")
        except Exception as e:
            print(f"绘图失败: {e}")

        # 生成可视化报告
        try:
            import report
            report.generate_report()
        except Exception as e:
            print(f"生成报告失败: {e}")


def main():
    """测试 - 使用config中的默认参数"""
    bt = Backtest()
    bt.run()


if __name__ == '__main__':
    main()
