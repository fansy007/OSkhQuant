# -*- coding: utf-8 -*-
"""
卖出策略模块 - 基本面止盈止损
根据配置文件中的条件进行卖出决策

配置文件: strategy/sell_fundamental_strategy.config
"""
import os

# 项目根目录（demo_claw）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'strategy', 'sell_fundamental_strategy.config')


def load_config():
    """加载卖出配置文件"""
    config = {
        'stop_loss': 0,      # 止损回撤比例(%)
        'take_profit': 0,    # 止盈盈利比例(%)
        'rebalance_days': 0, # 再平衡周期(天)，0表示不启用
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
            if len(parts) < 2:
                continue

            key = parts[0]
            value = parts[1]

            if key == 'stop_loss':
                config['stop_loss'] = float(value)
            elif key == 'take_profit':
                config['take_profit'] = float(value)
            elif key == 'rebalance_days':
                config['rebalance_days'] = int(value)

    return config


def stock_sell(positions: dict, current_date: str, new_buy_list: list, prices: dict, is_rebalance_day: bool = False) -> list:
    """股票卖出决策

    Args:
        positions: 持仓字典
        current_date: 当前日期
        new_buy_list: 最新选出的股票列表（仅在调仓日使用）
        prices: 当日价格
        is_rebalance_day: 是否是调仓日

    Returns:
        卖出列表: [(stock, reason, price, shares, profit), ...]
    """
    config = load_config()

    to_sell = []

    for stock, pos in positions.items():
        if stock not in prices:
            continue

        current_price = prices[stock]
        
        # 跳过价格无效的情况（NaN或None）
        if current_price is None or (isinstance(current_price, float) and current_price != current_price):
            continue
        cost = pos['cost']
        shares = pos['shares']
        peak_price = pos.get('peak_price', cost)

        # 更新最高价
        if current_price > peak_price:
            peak_price = current_price

        # 计算盈亏
        profit_pct = (current_price - cost) / cost * 100

        # 1. 止损检查（每天执行）
        if config['stop_loss'] > 0 and peak_price > 0:
            drawdown = (peak_price - current_price) / peak_price * 100
            if drawdown >= config['stop_loss']:
                profit = (current_price - cost) * shares
                to_sell.append((stock, '止损', current_price, shares, profit))
                continue

        # 2. 止盈检查（每天执行）
        if config['take_profit'] > 0 and profit_pct >= config['take_profit']:
            profit = (current_price - cost) * shares
            to_sell.append((stock, '止盈', current_price, shares, profit))
            continue

        # 3. 调仓日卖出（仅在调仓日执行）
        if is_rebalance_day and new_buy_list and stock not in new_buy_list:
            profit = (current_price - cost) * shares
            to_sell.append((stock, '调仓卖出', current_price, shares, profit))
            continue

    return to_sell


def get_sell_config():
    """获取卖出配置"""
    return load_config()


# 测试
if __name__ == '__main__':
    config = load_config()
    print(f"卖出配置: {config}")

    # 测试卖出逻辑
    positions = {
        '300001.SZ': {'shares': 1000, 'cost': 10.0, 'buy_date': '20240301', 'peak_price': 11.0},
        '300002.SZ': {'shares': 2000, 'cost': 8.0, 'buy_date': '20240301', 'peak_price': 8.5},
    }
    new_buy_list = ['300002.SZ', '300003.SZ']  # 300001不在新名单，会被调仓卖出
    prices = {
        '300001.SZ': 9.5,  # 从11跌到9.5，回撤13.6%，触发止损
        '300002.SZ': 9.0,  # 盈利12.5%
    }

    to_sell = stock_sell(positions, '20240317', new_buy_list, prices)
    print(f"\n卖出列表: {to_sell}")
