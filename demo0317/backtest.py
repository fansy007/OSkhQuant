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

PROJECT_ROOT = r'e:\workspace\OSkhQuant'
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')

# 输出路径
OUTPUT_DIR = os.path.join(PROJECT_ROOT, 'demo0317')


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
    """Get real trading dates (filter holidays)

    Args:
        start_date: start date
        end_date: end date
        xtdata: xtdata instance, if None use weekday filter

    Returns:
        list of real trading dates
    """

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
    """批量获取股票历史价格"""
    if not stock_list or not dates:
        return {}

    start_date = dates[0]
    end_date = dates[-1]

    # 下载数据
    try:
        xtdata.download_history_data2(
            stock_list=stock_list,
            period='1d',
            start_time=start_date,
            end_time=end_date
        )
    except:
        pass

    # 读取数据
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

    def __init__(self, initial_capital: int = 1000000,
                 start_date: str = '20240101',
                 end_date: str = '20250601'):
        """初始化

        Args:
            initial_capital: 初始资金
            start_date: 开始日期
            end_date: 结束日期
        """
        self.initial_capital = initial_capital
        self.start_date = start_date
        self.end_date = end_date

        # 加载模块
        import stock_buy, stock_sell
        self.stock_buy = stock_buy
        self.stock_sell = stock_sell

        # 配置
        self.buy_config = stock_buy.load_config()
        self.sell_config = stock_sell.load_config()

        # 状态
        self.cash = initial_capital
        self.positions = {}  # {stock: {'shares': xxx, 'cost': xxx, 'buy_date': xxx, 'peak_price': xxx}}
        self.trades = []  # 交易记录
        self.daily_assets = []  # 每日资产

        # 基准
        self.benchmark = self.sell_config.get('benchmark', '000905.SH')
        self.benchmark_prices = {}

    def run(self):
        """运行回测"""
        print("=" * 60)
        print(f" 回测系统")
        print("=" * 60)
        print(f"初始资金: {self.initial_capital:,}")
        print(f"回测期间: {self.start_date} - {self.end_date}")
        print(f"买入门槛: {self.buy_config.get('min_buy_amount', 0)}")
        print(f"止损: {self.sell_config.get('stop_loss', 0)}%")
        print(f"止盈: {self.sell_config.get('take_profit', 0)}%")
        print(f"再平衡: {self.sell_config.get('rebalance_days', 0)}天")
        print(f"基准: {self.benchmark}")

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
            # 计算是否是调仓日
            day_num = i + 1  # 第几个交易日
            rebalance_days = self.sell_config.get('rebalance_days', 0)
            is_rebalance_day = (rebalance_days > 0 and day_num % rebalance_days == 0)

            # 获取选股结果
            buy_result = self.stock_buy.stock_buy(date_str, xtdata)
            selected_stocks = buy_result.get('stocks', [])

            # 实时获取当日价格
            prices_data = get_stock_prices(xtdata, selected_stocks, [date_str])
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
                        del self.positions[stock]
                        self.cash += price * shares
                        self.trades.append({
                            'date': date_str, 'stock': stock, 'action': 'SELL',
                            'price': price, 'shares': shares, 'profit': profit, 'reason': reason
                        })

            # ========== 买入（每天有钱就买，复用选股结果） ==========
            if self.cash >= self.buy_config.get('min_buy_amount', 0):
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

            # 3. 记录当日资产（处理节假日：用上一个交易日的数据填充）
            # 计算持仓市值
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

            # 进度
            if (i + 1) % 20 == 0:
                print(f"  进度: {i+1}/{len(trading_dates)}, 资产: {total_value:,.0f}, 持仓: {len(self.positions)}")

        # 回测结束，使用最后一天的资产值
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

        # 基准对比
        if self.daily_assets and self.benchmark_prices:
            first_asset = self.daily_assets[0]
            last_asset = self.daily_assets[-1]
            if first_asset['benchmark_value'] and last_asset['benchmark_value']:
                benchmark_return = (last_asset['benchmark_value'] - first_asset['benchmark_value']) / first_asset['benchmark_value'] * 100
                print(f"\n基准对比 ({self.benchmark}):")
                print(f"  基准收益: {benchmark_return:.2f}%")
                print(f"  超额收益: {total_return - benchmark_return:.2f}%")

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
    """测试"""
    bt = Backtest(
        initial_capital=1000000,
        start_date='20260201',
        end_date='20260317'
    )
    bt.run()


if __name__ == '__main__':
    main()
