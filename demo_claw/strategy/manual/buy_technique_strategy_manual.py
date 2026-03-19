# -*- coding: utf-8 -*-
"""
买入策略模块 - 支持回测和实时选股
根据配置文件中的评分阈值进行买入决策

配置文件: strategy/buy_technique_strategy_manual.config

调用示例:
    # 1. 选股（根据配置的行业和阈值筛选）
    result = stock_buy()              # 实时选股
    result = stock_buy('20260319')    # 回测选股
    
    # 2. 获取Scorer自己打分
    scorer = get_scorer()                              # 自动判断盘中/盘后
    scorer = get_scorer(date='20260319')               # 强制回测模式
    scorer = get_scorer(date=None)                     # 强制实时模式
    
    # 3. 单股票打分
    result = score_single('300303.SZ')                 # 实时
    result = score_single('300303.SZ', '20260319')    # 回测
    
    # 4. 批量打分
    stocks = ['300303.SZ', '301361.SZ', '300708.SZ']
    batch_score(stocks)                      # 实时
    batch_score(stocks, '20260319')          # 回测
"""
import os
import sys
import importlib.util
from datetime import datetime

# 项目根目录（demo_claw）
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', '..', 'xtquant')
CONFIG_PATH = os.path.join(PROJECT_ROOT, 'manual', 'buy_technique_strategy_manual.config')

# 导入评分器
sys.path.insert(0, PROJECT_ROOT)
from manual.buy_scorer_manual import StockScorerManual


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
        'fundamental_weight': 0.4,        # 基本面权重
        'buy_score_threshold': 7.0,       # 综合分买入阈值
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


def is_trading_time():
    """判断是否在交易时段（盘中）"""
    now = datetime.now()
    if now.weekday() >= 5:  # 周末
        return False
    if now.hour >= 9 and now.hour < 15:
        if now.hour > 11 or (now.hour == 11 and now.minute < 30):
            return True
    return False


def get_scorer(date=None, xtdata=None):
    """工厂函数：获取评分器
    
    Args:
        date: 日期字符串，如 '20260319'
            - 传日期: 回测模式
            - 传 None: 自动判断（盘中实时，盘后回测）
        xtdata: xtquant数据对象（可选）
    
    Returns:
        StockScorerManual 实例
    """
    config = load_config()
    
    # 加载xtquant
    if xtdata is None:
        xtquant, xtdata = load_xtquant()
    
    # 判断模式
    if date is None:
        if is_trading_time():
            mode = 'realtime'
            date = datetime.now().strftime("%Y%m%d")
        else:
            mode = 'backtest'
            date = datetime.now().strftime("%Y%m%d")
    else:
        mode = 'backtest'
    
    print(f">>> {mode}模式, 日期: {date}")
    
    scorer = StockScorerManual(
        price_volume_weight=config['price_volume_weight'],
        fundamental_weight=config['fundamental_weight'],
        xtdata=xtdata
    )
    
    return scorer, date


def score_single(stock_code, date=None, xtdata=None):
    """单股票打分
    
    Args:
        stock_code: 股票代码，如 '300303.SZ'
        date: 日期（可选）
            - 传日期: 回测模式
            - 传 None: 自动判断
        xtdata: xtquant数据对象（可选）
    
    Returns:
        dict: 评分结果
    """
    scorer, actual_date = get_scorer(date, xtdata)
    
    # 预下载数据
    scorer.preload_data([stock_code], actual_date)
    
    # 评分
    result = scorer.score(stock_code, date=actual_date)
    scorer.print_report(result)
    return result


def batch_score(stock_list, date=None, xtdata=None):
    """批量股票打分
    
    Args:
        stock_list: 股票代码列表，如 ['300303.SZ', '301361.SZ']
        date: 日期（可选）
            - 传日期: 回测模式
            - 传 None: 自动判断
        xtdata: xtquant数据对象（可选）
    
    Returns:
        list: 评分结果列表（按综合分降序）
    """
    if not stock_list:
        return []
    
    scorer, actual_date = get_scorer(date, xtdata)
    
    # 预下载数据
    scorer.preload_data(stock_list, actual_date)
    
    # 批量评分
    results = []
    for stock in stock_list:
        try:
            result = scorer.score(stock, date=actual_date)
            scorer.print_report(result)
            results.append(result)
        except Exception as e:
            print(f"  评分失败 {stock}: {e}")
            results.append({'code': stock, 'error': str(e)})
    
    # 按综合分排序
    results.sort(key=lambda x: x.get('composite_score', 0), reverse=True)
    return results


def stock_buy(date: str = None, xtdata=None) -> dict:
    """股票买入主函数

    Args:
        date: 日期（可选）
            - 传入日期如 '20250317': 回测模式
            - 不传或传 None: 实时模式（获取今天数据）
        xtdata: xtquant数据对象（可选）

    Returns:
        {
            'stocks': ['300xxx.SZ', ...],  # 选出的股票（按评分排序）
            'date': '20250317',             # 选股日期
            'mode': 'backtest' or 'realtime',  # 模式
            'prices': {'300xxx.SZ': 10.5, ...},  # 当日收盘价/实时价
            'scores': {'300xxx.SZ': 7.5, ...},    # 综合评分
            'config': config                # 配置信息
        }
    """
    # 加载配置
    config = load_config()

    # 加载xtquant
    if xtdata is None:
        xtquant, xtdata = load_xtquant()

    # 判断模式
    if date is None:
        mode = 'realtime'
        date_str = '实时'
    else:
        mode = 'backtest'
        date_str = date

    print(f"\n{'='*60}")
    print(f"买入策略 ({mode}模式), 日期: {date_str}")
    print(f"{'='*60}")

    # 1. 获取股票池
    if config['stock_pool']:
        stock_list = config['stock_pool']
    elif config['industry']:
        stock_list = get_stocks_by_industry(xtdata, config['industry'])
    else:
        print("未配置股票池或行业，无法选股")
        return {'stocks': [], 'date': date, 'mode': mode, 'prices': {}, 'scores': {}, 'config': config}

    if not stock_list:
        return {'stocks': [], 'date': date, 'mode': mode, 'prices': {}, 'scores': {}, 'config': config}

    print(f"  股票池数量: {len(stock_list)}")

    # 2. 初始化评分器（传入xtdata避免重复加载）
    scorer = StockScorerManual(
        price_volume_weight=config['price_volume_weight'],
        fundamental_weight=config['fundamental_weight'],
        xtdata=xtdata
    )

    # 3. 批量预下载所有股票数据
    scorer.preload_data(stock_list, date)

    # 4. 对所有股票评分
    scored_stocks = []

    for stock in stock_list:
        try:
            result = scorer.score(stock, date=date)

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
        'date': date,
        'mode': mode,
        'prices': prices,
        'scores': scores,
        'config': config
    }


def get_buy_config():
    """获取买入配置"""
    return load_config()


# ========== 测试代码 ==========
if __name__ == '__main__':


    ######################################## 实时选股
    # result = stock_buy()
    #
    # # 打印结果
    # print("\n=== 选股结果 ===")
    # print(f"模式: {result.get('mode')}")
    # print(f"选中数量: {len(result.get('stocks', []))}")
    # print(f"股票列表: {result.get('stocks', [])}")
    # print(f"评分: {result.get('scores', {})}")

    #######################################
    # 4. 批量打分
    stocks = ['300017.SZ','002335.SZ','300442.SZ','002518.SZ','300113.SZ']
    batch_score(stocks)                      # 实时
    # batch_score(stocks, '20260319')          # 回测

