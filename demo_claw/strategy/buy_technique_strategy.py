# -*- coding: utf-8 -*-
"""
买入策略模块 - 基于三维评分系统
根据配置文件中的评分阈值进行买入决策

配置文件: strategy/buy_technique_strategy.config
"""
import os
import sys
import importlib.util

# 项目根目录（demo_claw）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', 'xtquant')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'strategy', 'buy_technique_strategy.config')

# 导入评分器
sys.path.insert(0, os.path.join(PROJECT_ROOT, 'strategy'))
from buy_scorer import StockScorer


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
    """加载买入配置文件"""
    config = {
        'price_volume_weight': 0.6,      # 量价形态权重
        'fundamental_weight': 0.4,       # 基本面权重
        'buy_score_threshold': 7.0,      # 综合分买入阈值
        'industry': None,                # 行业条件
        'stock_pool': [],                # 股票池（空列表表示按行业选）
    }

    if not os.path.exists(CONFIG_PATH):
        print(f"配置文件不存在: {CONFIG_PATH}，使用默认配置")
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

            if key == 'price_volume_weight':
                config['price_volume_weight'] = float(value)
            elif key == 'fundamental_weight':
                config['fundamental_weight'] = float(value)
            elif key == 'buy_score_threshold':
                config['buy_score_threshold'] = float(value)
            elif key == 'industry':
                if value:
                    config['industry'] = value
            elif key == 'stock_pool':
                if value:
                    config['stock_pool'] = [s.strip() for s in value.split(',')]

    return config


def get_stocks_by_industry(xtdata, industry_name: str) -> list:
    """获取指定行业的所有股票"""
    stock_list = xtdata.get_stock_list_in_sector(industry_name)
    if not stock_list:
        print(f"  未找到行业: {industry_name}")
        return []
    return stock_list


def stock_buy(report_date: str, xtdata=None) -> dict:
    """股票买入主函数

    Args:
        report_date: 回测日期，格式如 '20250317'
        xtdata: xtquant数据对象（可选）

    Returns:
        {
            'stocks': ['300xxx.SZ', ...],  # 选出的股票（按评分排序）
            'date': '20250317',             # 选股日期
            'prices': {'300xxx.SZ': 10.5, ...},  # 当日收盘价
            'scores': {'300xxx.SZ': 7.5, ...},    # 综合评分
            'config': config                # 配置信息
        }
    """
    # 加载配置
    config = load_config()

    # 加载xtquant
    if xtdata is None:
        xtquant, xtdata = load_xtquant()

    # 1. 获取股票池
    if config['stock_pool']:
        stock_list = config['stock_pool']
    elif config['industry']:
        stock_list = get_stocks_by_industry(xtdata, config['industry'])
    else:
        print("未配置股票池或行业，无法选股")
        return {'stocks': [], 'date': report_date, 'prices': {}, 'scores': {}, 'config': config}

    if not stock_list:
        return {'stocks': [], 'date': report_date, 'prices': {}, 'scores': {}, 'config': config}

    print(f"  股票池数量: {len(stock_list)}")

    # 2. 初始化评分器（传入xtdata避免重复加载）
    scorer = StockScorer(
        price_volume_weight=config['price_volume_weight'],
        fundamental_weight=config['fundamental_weight'],
        xtdata=xtdata
    )

    # 3. 批量预下载所有股票数据
    scorer.preload_data(stock_list, report_date)

    # 4. 对所有股票评分
    scored_stocks = []

    for stock in stock_list:
        try:
            result = scorer.score(stock, date=report_date)

            composite_score = result['composite_score']
            pv_score = result['price_volume_score']
            fund_score = result['fundamental_score']
            current_price = result['details']['price_volume']['signals'].get('current_price', 0)

            # 检查是否满足买入条件
            if composite_score < config['buy_score_threshold']:
                continue

            scored_stocks.append({
                'stock': stock,
                'score': composite_score,
                'pv_score': pv_score,
                'fund_score': fund_score,
                'price': current_price
            })

        except Exception:
            continue  # 跳过评分为0或失败的股票

    # 5. 按评分排序（不设上限，所有满足条件的都选）
    scored_stocks.sort(key=lambda x: x['score'], reverse=True)

    # 6. 组装返回结果
    stocks = [s['stock'] for s in scored_stocks]
    prices = {s['stock']: s['price'] for s in scored_stocks}
    scores = {s['stock']: s['score'] for s in scored_stocks}

    print(f"  选中股票: {len(scored_stocks)} 只")
    for s in scored_stocks[:10]:  # 只打印前10只
        print(f"    {s['stock']}: 综合分={s['score']}, 量价={s['pv_score']}, 基本面={s['fund_score']}, 价格={s['price']}")
    if len(scored_stocks) > 10:
        print(f"    ... 还有 {len(scored_stocks) - 10} 只")

    return {
        'stocks': stocks,
        'date': report_date,
        'prices': prices,
        'scores': scores,
        'config': config
    }


def get_buy_config():
    """获取买入配置"""
    return load_config()


# 测试
if __name__ == '__main__':
    result = stock_buy('20250317')
    print(f"\n选股结果: {result['stocks']}")
    print(f"当日价格: {result['prices']}")
    print(f"综合评分: {result['scores']}")
