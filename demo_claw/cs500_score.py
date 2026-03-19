# -*- coding: utf-8 -*-
"""
CS500 市场环境自动评分系统
每天自动计算中证500的市场环境状态

输出:
- PE百分位 (历史PE估值)
- 成交量比 (5日均量/120日均量)
- 20日涨幅 
- 融资余额变化 (如果有数据)
- 综合评分 (0-10分)
- 市场状态: 冷/转暖/热
"""

import sys
sys.path.insert(0, 'E:\\')
from xtquant import xtdata
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# ========== 配置区 ==========
INDEX_CODE = '000905.SH'  # 中证500指数
OUTPUT_FILE = 'C:\\Users\\qjgeng\\Desktop\\cs500_score_result.txt'


def get_index_data():
    """获取指数数据"""
    # 获取日线数据
    data = xtdata.get_market_data_ex(
        field_list=['time', 'close', 'volume', 'open', 'high', 'low'],
        stock_list=[INDEX_CODE],
        period='1d',
        start_time='20240101',
        end_time=datetime.now().strftime('%Y%m%d'),
        count=-1
    )
    
    if INDEX_CODE not in data or data[INDEX_CODE] is None:
        return None
    
    df = data[INDEX_CODE].copy()
    df['date'] = pd.to_datetime(df['time'], unit='ms')
    df = df.set_index('date').sort_index()
    
    return df


def calculate_pe_percentile(df):
    """
    计算PE百分位
    简化版：用近5年PE历史分位数
    如果无法获取PE数据，用PB近似
    """
    # 尝试获取PE数据
    try:
        # 简单模拟：假设当前PE在历史区间的位置
        # 实际应该从QMT获取PE历史数据
        # 这里先用价格波动近似
        current_price = df['close'].iloc[-1]
        prices_5y = df['close'].tail(252*5)  # 5年数据
        
        if len(prices_5y) > 0:
            percentile = (current_price - prices_5y.min()) / (prices_5y.max() - prices_5y.min()) * 100
            return round(percentile, 1)
    except:
        pass
    
    return None


def calculate_volume_ratio(df):
    """计算成交量比: 5日均量 / 120日均量"""
    vol_5d = df['volume'].tail(5).mean()
    vol_120d = df['volume'].tail(120).mean()
    
    if vol_120d > 0:
        ratio = vol_5d / vol_120d
        return round(ratio, 2)
    return None


def calculate_20day_return(df):
    """计算20日涨幅"""
    if len(df) >= 20:
        current = df['close'].iloc[-1]
        past_20d = df['close'].iloc[-20]
        ret = (current - past_20d) / past_20d * 100
        return round(ret, 2)
    return None


def get_margin_data():
    """
    获取融资融券数据
    中证500成分股的融资余额总和作为市场融资情绪指标
    """
    # 这个需要从QMT获取融资融券数据
    # 简化版：返回None表示无数据
    return None


def score_indicator(value, thresholds_cold, thresholds_warm):
    """
    给单个指标打分
    返回: 分数 (0-10) 和状态 (冷/转暖/热)
    
    thresholds_cold: (冷阈值, 转暖阈值)
    thresholds_warm: (转暖阈值, 热阈值)
    """
    if value is None:
        return 5, '未知'
    
    cold_thresh, warm_thresh = thresholds_cold
    warm_thresh2, hot_thresh = thresholds_warm
    
    if value < cold_thresh:
        # 冷
        score = 10 - (value / cold_thresh) * 2
        return max(8, min(10, round(score, 1))), '冷'
    elif value < warm_thresh:
        # 转暖
        score = 8 - ((value - cold_thresh) / (warm_thresh - cold_thresh)) * 3
        return max(5, min(8, round(score, 1))), '转暖'
    elif value < warm_thresh2:
        # 正常
        return 5, '正常'
    else:
        # 热
        score = 5 - ((value - warm_thresh2) / (hot_thresh - warm_thresh2)) * 5
        return max(0, min(5, round(score, 1))), '热'


def calculate_cs500_score():
    """计算CS500综合评分"""
    
    # 连接QMT
    print("正在连接QMT...")
    xtdata.connect()
    
    # 获取数据
    print("正在获取中证500数据...")
    df = get_index_data()
    
    if df is None or len(df) < 120:
        print("数据不足，无法计算")
        return
    
    # 计算各指标
    print("正在计算指标...")
    
    # 1. PE百分位 (简化版，用价格位置近似)
    # 实际应该用PE数据
    pe_percentile = calculate_pe_percentile(df)
    pe_score, pe_status = score_indicator(
        pe_percentile, 
        (30, 60),  # 冷<30, 转暖30-60
        (60, 80)   # 正常60, 热>60
    )
    
    # 2. 成交量比
    vol_ratio = calculate_volume_ratio(df)
    vol_score, vol_status = score_indicator(
        vol_ratio,
        (0.8, 1.2),  # 冷<0.8, 转暖0.8-1.2
        (1.2, 1.5)   # 正常1.2, 热>1.5
    )
    
    # 3. 20日涨幅
    ret_20d = calculate_20day_return(df)
    ret_score, ret_status = score_indicator(
        ret_20d,
        (-5, 5),    # 冷<-5%, 转暖-5%~+5%
        (5, 10)     # 正常+5%, 热>+10%
    )
    
    # 4. 融资余额 (如果有数据)
    margin_data = get_margin_data()
    if margin_data:
        margin_score, margin_status = score_indicator(
            margin_data,
            (-10, 10),  # 冷: 下降, 转暖: -10%~+10%
            (10, 20)    # 正常: +10%, 热: >+20%
        )
    else:
        margin_score, margin_status = None, '无数据'
    
    # 综合评分 (平均)
    scores = [pe_score, vol_score, ret_score]
    if margin_score is not None:
        scores.append(margin_score)
    
    total_score = np.mean(scores)
    
    # 市场状态判断
    if total_score >= 7:
        market_status = "冷 - 适合买入"
    elif total_score >= 5:
        market_status = "转暖 - 谨慎买入"
    elif total_score >= 3:
        market_status = "正常 - 观望"
    else:
        market_status = "热 - 暂停买入"
    
    # 判断是否过热 (禁止买入)
    if total_score <= 3:
        buy_recommendation = "暂停买入"
    elif total_score <= 5:
        buy_recommendation = "轻仓买入"
    else:
        buy_recommendation = "正常买入"
    
    # 输出结果
    result = f"""
{'='*50}
CS500 市场环境评分
{'='*50}
评分日期: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
中证500指数: {INDEX_CODE}
最新收盘价: {df['close'].iloc[-1]:.2f}

{'='*50}
一、PE百分位 (估值)
{'='*50}
当前值: {pe_percentile:.1f}% (如果有PE数据)
状态: {pe_status}
得分: {pe_score}/10

{'='*50}
二、成交量比 (5日均量/120日均量)
{'='*50}
当前值: {vol_ratio:.2f}
状态: {vol_status}
得分: {vol_score}/10

{'='*50}
三、20日涨幅 (动量)
{'='*50}
当前值: {ret_20d:.2f}%
状态: {ret_status}
得分: {ret_score}/10

{'='*50}
四、融资余额变化
{'='*50}
状态: {margin_status}
得分: {margin_score}/10 if margin_score else '无数据'

{'='*50}
综合评分
{'='*50}
总分: {total_score:.1f}/10
市场状态: {market_status}
买入建议: {buy_recommendation}

{'='*50}
系统说明
{'='*50}
CS500评分 > 7分: 冷/转暖 - 执行三维买入
CS500评分 ≤ 7分: 热/正常 - 暂停/减少买入
"""
    
    print(result)
    
    # 保存到文件
    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        f.write(result)
    
    print(f"\n结果已保存到: {OUTPUT_FILE}")
    
    return {
        'score': total_score,
        'status': market_status,
        'recommendation': buy_recommendation,
        'pe': pe_percentile,
        'volume_ratio': vol_ratio,
        'return_20d': ret_20d
    }


if __name__ == '__main__':
    calculate_cs500_score()
