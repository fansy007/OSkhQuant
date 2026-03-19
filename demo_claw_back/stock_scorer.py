# -*- coding: utf-8 -*-
"""
StockScorer - 三维买入评估系统 v3.1

两个类：
- StockScorer: 回测用，传入具体日期，用历史收盘数据
- StockScorerRealtime: 盘中实时，自动获取今天数据并预估成交量

Usage:
    # 回测
    scorer = StockScorer(price_volume_weight=0.6, fundamental_weight=0.4)
    result = scorer.score("600519.SH", date="20250317")
    
    # 实时
    realtime_scorer = StockScorerRealtime(price_volume_weight=0.6, fundamental_weight=0.4)
    result = realtime_scorer.score("600519.SH")
"""
import sys
import os
import importlib.util
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 项目根目录
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
XTQUANT_PATH = os.path.join(PROJECT_ROOT, 'xtquant')


def load_xtquant():
    """加载xtquant"""
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


class StockScorer:
    """股票评分器 - 用于回测"""
    
    def __init__(self, price_volume_weight=0.6, fundamental_weight=0.4):
        """
        初始化评分器
        
        Args:
            price_volume_weight: 量价形态权重，默认0.6
            fundamental_weight: 基本面权重，默认0.4
        """
        if abs(price_volume_weight + fundamental_weight - 1.0) > 0.001:
            raise ValueError(f"权重之和必须等于1，当前：{price_volume_weight + fundamental_weight}")
        
        self.pv_weight = price_volume_weight
        self.fund_weight = fundamental_weight
        self.xtquant, self.xtdata = load_xtquant()
    
    def score(self, stock_code, date):
        """
        对股票进行评分（回测用）
        
        Args:
            stock_code: 股票代码，如 "600519.SH"
            date: 日期，格式 "YYYYMMDD"
        
        Returns:
            dict: 评分结果
        """
        print(f"\n{'='*60}")
        print(f"评分股票: {stock_code}")
        print(f"评分日期: {date}")
        print(f"{'='*60}")
        
        # 1. 获取K线数据
        kline_df = self._get_kline(stock_code, date)
        fin_data = self._get_financial(stock_code, date)
        
        # 2. 计算各维度分数
        pv_result = self._calc_price_volume_score(kline_df)
        fund_result = self._calc_fundamental_score(fin_data)
        
        # 3. 计算综合分
        composite = pv_result["score"] * self.pv_weight + fund_result["score"] * self.fund_weight
        
        # 4. 建议
        if composite >= 8.0:
            recommendation = "强烈买入"
        elif composite >= 7.0:
            recommendation = "正常买入"
        elif composite >= 6.0:
            recommendation = "轻仓试错"
        elif composite >= 4.0:
            recommendation = "中性观望"
        else:
            recommendation = "不买入"
        
        result = {
            "code": stock_code,
            "name": self._get_stock_name(stock_code),
            "date": date,
            "composite_score": round(composite, 1),
            "price_volume_score": pv_result["score"],
            "fundamental_score": fund_result["score"],
            "recommendation": recommendation,
            "details": {
                "price_volume": pv_result,
                "fundamental": fund_result
            }
        }
        
        self._print_result(result)
        return result
    
    def _get_kline(self, stock_code, date, days=120):
        """获取K线数据（回测用）"""
        start_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")
        
        try:
            # 下载历史数据
            self.xtdata.download_history_data2(
                stock_list=[stock_code],
                period='1d',
                start_time=start_date,
                end_time=date
            )
            
            # 获取数据
            data = self.xtdata.get_market_data_ex(
                field_list=['time', 'open', 'high', 'low', 'close', 'volume'],
                stock_list=[stock_code],
                period='1d',
                start_time=start_date,
                end_time=date
            )
            
            if stock_code not in data or data[stock_code] is None:
                return None
            
            df = data[stock_code].copy()
            df['date'] = pd.to_datetime(df['time'], unit='ms')
            df = df.set_index('date').sort_index()
            df = df[df.index <= pd.to_datetime(date)]
            df = df.tail(days)
            
            return df
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return None
    
    def _get_financial(self, stock_code, date):
        """获取财务数据 - 先下载到本地再读取"""
        try:
            # 1. 先下载财务数据到本地
            print(f"  正在下载财务数据...")
            self.xtdata.download_financial_data2(
                stock_list=[stock_code],
                table_list=['Income', 'CashFlow']
            )
            
            # 2. 从本地获取财务数据（取大范围确保有足够历史数据）
            year = int(date[:4])
            start_time = f"{year-3}0101"
            end_time = f"{year+1}1231"
            
            result = self.xtdata.get_financial_data(
                stock_list=[stock_code],
                table_list=['Income', 'CashFlow'],
                start_time=start_time,
                end_time=end_time,
                report_type='announce_time'
            )
            
            if not result or stock_code not in result:
                print(f"  未获取到财务数据")
                return None
            
            tables = result[stock_code]
            
            # 解析Income表
            income_df = tables.get('Income', pd.DataFrame())
            if income_df.empty:
                print(f"  Income表为空")
                return None
            
            # 确定日期列名
            date_col = 'endDate' if 'endDate' in income_df.columns else 'm_timetag'
            if date_col not in income_df.columns:
                print(f"  未找到日期列，可用列: {list(income_df.columns)[:10]}")
                return None
            
            # 处理日期格式
            def parse_date(val):
                if pd.isna(val):
                    return None
                if isinstance(val, (int, float)):
                    try:
                        return datetime.fromtimestamp(val / 1000).strftime('%Y%m%d')
                    except:
                        return None
                elif isinstance(val, str):
                    return val[:8] if len(val) >= 8 else val
                return None
            
            income_df['parsed_date'] = income_df[date_col].apply(parse_date)
            
            # 获取所有可用日期
            available_dates = income_df['parsed_date'].dropna().unique()
            available_dates = sorted([d for d in available_dates if d is not None], reverse=True)
            if not available_dates:
                print(f"  未找到任何财报数据")
                return None
            
            # 确定目标年报日期：优先N-1年，没有就N-2年
            report_date = self._get_latest_report_date(date, available_dates)
            
            # 获取本期数据
            current = income_df[income_df['parsed_date'] == report_date]
            if current.empty:
                print(f"  未找到{report_date}的财报")
                return None
            
            revenue = current['revenue'].iloc[0] if 'revenue' in current.columns else 0
            net_profit_deducted = current['net_profit_incl_min_int_inc_after'].iloc[0] if 'net_profit_incl_min_int_inc_after' in current.columns else 0
            
            # 处理NaN
            if pd.isna(revenue):
                revenue = 0
            if pd.isna(net_profit_deducted):
                net_profit_deducted = 0
            
            # 获取去年同期数据
            last_year_date = f"{int(report_date[:4])-1}1231"
            last_year = income_df[income_df['parsed_date'] == last_year_date]
            
            revenue_last = last_year['revenue'].iloc[0] if not last_year.empty and 'revenue' in last_year.columns else 0
            net_profit_deducted_last = last_year['net_profit_incl_min_int_inc_after'].iloc[0] if not last_year.empty and 'net_profit_incl_min_int_inc_after' in last_year.columns else 0
            
            if pd.isna(revenue_last):
                revenue_last = 0
            if pd.isna(net_profit_deducted_last):
                net_profit_deducted_last = 0
            
            # 获取现金流
            cashflow_df = tables.get('CashFlow', pd.DataFrame())
            operating_cash_flow = 0
            if not cashflow_df.empty:
                cash_date_col = 'endDate' if 'endDate' in cashflow_df.columns else 'm_timetag'
                if cash_date_col in cashflow_df.columns:
                    cashflow_df['parsed_date'] = cashflow_df[cash_date_col].apply(parse_date)
                    cash_current = cashflow_df[cashflow_df['parsed_date'] == report_date]
                    if not cash_current.empty and 'net_cash_flows_oper_act' in cash_current.columns:
                        operating_cash_flow = cash_current['net_cash_flows_oper_act'].iloc[0]
                        if pd.isna(operating_cash_flow):
                            operating_cash_flow = 0
            
            print(f"  财务数据获取成功:")
            print(f"    财报日期: {report_date}")
            print(f"    营收: {revenue/1e8:.2f}亿 (去年: {revenue_last/1e8:.2f}亿)")
            print(f"    扣非净利: {net_profit_deducted/1e8:.2f}亿 (去年: {net_profit_deducted_last/1e8:.2f}亿)")
            print(f"    经营现金流: {operating_cash_flow/1e8:.2f}亿")
            
            return {
                "revenue": float(revenue) if revenue else 0,
                "revenue_last": float(revenue_last) if revenue_last else 0,
                "net_profit_deducted": float(net_profit_deducted) if net_profit_deducted else 0,
                "net_profit_deducted_last": float(net_profit_deducted_last) if net_profit_deducted_last else 0,
                "operating_cash_flow": float(operating_cash_flow) if operating_cash_flow else 0,
                "report_date": report_date
            }
        except Exception as e:
            print(f"获取财务数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def _get_latest_report_date(self, check_date, available_dates=None):
        """
        返回最新可用的年报日期
        策略：永远优先拿N-1年的年报，如果没有就拿N-2年的
        """
        year = int(check_date[:4])
        
        # 优先N-1年
        target_year = year - 1
        target_date = f"{target_year}1231"
        
        if available_dates:
            annual_reports = sorted([d for d in available_dates if d.endswith('1231')], reverse=True)
            # 找N-1年的年报
            for d in annual_reports:
                if d.startswith(str(target_year)):
                    return d
            # 没有N-1年，找N-2年
            for d in annual_reports:
                if d.startswith(str(target_year - 1)):
                    return d
            # 还没有，返回最新的年报
            if annual_reports:
                return annual_reports[0]
        
        return target_date
    
    def _get_stock_name(self, stock_code):
        """获取股票名称"""
        try:
            name = self.xtdata.get_stock_name(stock_code)
            return name if name else stock_code
        except:
            return stock_code
    
    def _calc_price_volume_score(self, df):
        """计算量价形态分"""
        if df is None or len(df) < 20:
            return {"score": 0, "details": {}, "description": "数据不足"}
        
        close = df['close']
        volume = df['volume']
        
        # 10日峰值（历史，不含今天）
        vol_10peak = volume.tail(10).max()
        vol_10peak_date = volume.tail(10).idxmax().strftime('%Y-%m-%d')
        current_vol = volume.iloc[-1]
        vol_ratio = current_vol / vol_10peak if vol_10peak > 0 else 1
        
        # 10日最高价
        price_10peak = close.tail(10).max()
        drawdown = (close.iloc[-1] - price_10peak) / price_10peak if price_10peak > 0 else 0
        
        # MA20
        ma20 = close.rolling(20).mean()
        ma20_current = ma20.iloc[-1]
        ma20_slope = (ma20.iloc[-1] - ma20.iloc[-2]) / ma20.iloc[-2] if len(ma20) >= 2 and ma20.iloc[-2] != 0 else 0
        
        # 当日涨跌
        pct_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) >= 2 else 0
        is_declining = pct_change < 0
        
        # 评分逻辑
        score = 0
        description = ""
        
        if vol_ratio < 0.30 and drawdown < -0.15 and ma20_slope > 0:
            score = 10
            description = "完美缩量回调：极度缩量(<30%)+深度回撤(>15%)+趋势向上"
        elif vol_ratio < 0.30 and drawdown < -0.10 and ma20_slope > 0:
            score = 9
            description = "优秀缩量回调：极度缩量(<30%)+较大回撤(>10%)+趋势向上"
        elif vol_ratio < 0.50 and drawdown < -0.10 and ma20_slope > 0:
            score = 8
            description = "理想缩量回调：缩量(<50%)+回撤>10%+趋势向上"
        elif vol_ratio < 0.50 and drawdown < -0.08 and ma20_slope > 0:
            score = 7
            description = "较好缩量回调：缩量(<50%)+回撤>8%+趋势向上"
        elif vol_ratio < 0.70 and drawdown < -0.05:
            score = 6
            description = "一般缩量回调：缩量(<70%)+小幅回撤(>5%)"
        elif vol_ratio < 0.70:
            score = 5
            description = "缩量状态(<70%)"
        elif vol_ratio <= 1.0:
            if is_declining:
                score = 4
                description = "缩量下跌，正常调整"
            else:
                score = 3
                description = "正常成交量"
        else:
            if pct_change > 0:
                score = 2
                description = "放量上涨，注意追高风险"
            else:
                score = 1
                description = "放量下跌，抛压沉重"
        
        return {
            "score": score,
            "signals": {
                "vol_ratio": round(vol_ratio, 2),
                "vol_10peak": int(vol_10peak),
                "vol_10peak_date": vol_10peak_date,
                "current_volume": int(current_vol),
                "drawdown_pct": round(drawdown * 100, 1),
                "price_10peak": round(price_10peak, 2),
                "current_price": round(close.iloc[-1], 2),
                "ma20": round(ma20_current, 2),
                "ma20_slope_pct": round(ma20_slope * 100, 2),
                "pct_change_pct": round(pct_change * 100, 2),
            },
            "description": description
        }
    
    def _calc_fundamental_score(self, fin_data):
        """计算基本面分"""
        if fin_data is None:
            return {"score": 5, "details": {}, "description": "财务数据缺失，默认5分"}
        
        revenue = fin_data.get("revenue", 0)
        revenue_last = fin_data.get("revenue_last", 0)
        profit = fin_data.get("net_profit_deducted", 0)
        profit_last = fin_data.get("net_profit_deducted_last", 0)
        cash_flow = fin_data.get("operating_cash_flow", 0)
        
        # 防止除零
        if revenue_last <= 0:
            revenue_last = revenue if revenue > 0 else 1
        if profit_last <= 0:
            profit_last = profit if profit > 0 else 1
        
        # 计算增速
        revenue_growth = (revenue - revenue_last) / revenue_last
        profit_growth = (profit - profit_last) / profit_last
        
        # 判断
        cash_flow_positive = cash_flow > 0
        revenue_growing = revenue_growth > 0
        profit_growing = profit_growth > 0
        both_growing = revenue_growing and profit_growing
        
        # 评分逻辑
        score = 0
        description = ""
        
        # 现金流为负的情况
        if not cash_flow_positive:
            if both_growing and revenue_growth > 0.20 and profit_growth > 0.20:
                score = 6
                description = f"双增长>20%但现金流为负"
            elif both_growing:
                score = 4
                description = f"双增长但现金流为负"
            else:
                score = 1
                description = f"现金流为负且增长乏力"
        
        # 现金流为正，正常评分
        else:
            if both_growing and revenue_growth > 0.20 and profit_growth > 0.20:
                score = 10
                description = f"优秀：双增长>20%，现金流为正"
            elif both_growing and revenue_growth > 0.20:
                score = 9
                description = f"营收增长>20%，现金流为正"
            elif both_growing and profit_growth > 0.20:
                score = 9
                description = f"扣非净利增长>20%，现金流为正"
            elif both_growing:
                if revenue_growth > 0.15 and profit_growth > 0.15:
                    score = 8
                    description = f"双增长，增速较高"
                else:
                    score = 7
                    description = f"双增长5-20%，现金流为正"
            elif revenue_growing or profit_growing:
                if revenue_growing:
                    score = 6
                    description = f"营收增长，净利下滑"
                else:
                    score = 5
                    description = f"净利增长，营收下滑"
            elif revenue_growth > -0.01 and revenue_growth < 0.05 and profit_growth > -0.01 and profit_growth < 0.05:
                score = 4
                description = f"低个位数增长或持平"
            else:
                score = 2
                description = f"营收或净利下滑"
        
        return {
            "score": score,
            "signals": {
                "revenue": revenue / 1e8,
                "revenue_last": revenue_last / 1e8,
                "revenue_growth_pct": round(revenue_growth * 100, 1),
                "profit_deducted": profit / 1e8,
                "profit_deducted_last": profit_last / 1e8,
                "profit_growth_pct": round(profit_growth * 100, 1),
                "operating_cash_flow": cash_flow / 1e8,
                "cash_flow_positive": cash_flow_positive,
                "report_date": fin_data.get("report_date", "")
            },
            "description": description
        }
    
    def _print_result(self, result):
        """打印评分结果"""
        print(f"\n【评分结果】")
        print(f"  综合分: {result['composite_score']}/10  ({result['recommendation']})")
        print(f"  量价形态: {result['price_volume_score']}/10")
        print(f"  基本面: {result['fundamental_score']}/10")
        
        pv = result['details']['price_volume']
        print(f"\n【量价形态详情】")
        print(f"  得分: {pv['score']}/10")
        print(f"  描述: {pv['description']}")
        if 'signals' in pv:
            sig = pv['signals']
            print(f"  当天成交量: {sig.get('current_volume', 'N/A'):,}")
            print(f"  10日峰值: {sig.get('vol_10peak', 'N/A'):,} ({sig.get('vol_10peak_date', 'N/A')})")
            print(f"  成交量比: {sig.get('vol_ratio', 'N/A')}")
            print(f"  回撤: {sig.get('drawdown_pct', 'N/A')}%")
            print(f"  MA20: {sig.get('ma20', 'N/A')}")
        
        fund = result['details']['fundamental']
        print(f"\n【基本面详情】")
        print(f"  得分: {fund['score']}/10")
        print(f"  描述: {fund['description']}")
        if 'signals' in fund and fund['signals']:
            sig = fund['signals']
            print(f"  财报日期: {sig.get('report_date', 'N/A')}")
            print(f"  营收: {sig.get('revenue', 'N/A'):.2f}亿 (去年: {sig.get('revenue_last', 'N/A'):.2f}亿, 增速: {sig.get('revenue_growth_pct', 'N/A')}%)")
            print(f"  扣非净利: {sig.get('profit_deducted', 'N/A'):.2f}亿 (去年: {sig.get('profit_deducted_last', 'N/A'):.2f}亿, 增速: {sig.get('profit_growth_pct', 'N/A')}%)")
            print(f"  经营现金流: {sig.get('operating_cash_flow', 'N/A'):.2f}亿")
        
        print(f"\n{'='*60}\n")


class StockScorerRealtime(StockScorer):
    """股票实时评分器 - 用于盘中"""
    
    def score(self, stock_code):
        """
        对股票进行实时评分（盘中用）
        
        Args:
            stock_code: 股票代码，如 "600519.SH"
        
        Returns:
            dict: 评分结果
        """
        today = datetime.now().strftime("%Y%m%d")
        
        print(f"\n{'='*60}")
        print(f"实时评分股票: {stock_code}")
        print(f"今天: {today}")
        print(f"{'='*60}")
        
        # 1. 获取K线数据（含实时更新）和财务数据
        kline_df = self._get_kline_realtime(stock_code)
        fin_data = self._get_financial(stock_code, today)
        
        # 2. 计算各维度分数
        pv_result = self._calc_price_volume_score_realtime(kline_df)
        fund_result = self._calc_fundamental_score(fin_data)
        
        # 3. 计算综合分
        composite = pv_result["score"] * self.pv_weight + fund_result["score"] * self.fund_weight
        
        # 4. 建议
        if composite >= 8.0:
            recommendation = "强烈买入"
        elif composite >= 7.0:
            recommendation = "正常买入"
        elif composite >= 6.0:
            recommendation = "轻仓试错"
        elif composite >= 4.0:
            recommendation = "中性观望"
        else:
            recommendation = "不买入"
        
        result = {
            "code": stock_code,
            "name": self._get_stock_name(stock_code),
            "date": today,
            "composite_score": round(composite, 1),
            "price_volume_score": pv_result["score"],
            "fundamental_score": fund_result["score"],
            "recommendation": recommendation,
            "details": {
                "price_volume": pv_result,
                "fundamental": fund_result
            }
        }
        
        self._print_result(result)
        return result
    
    def _get_kline_realtime(self, stock_code, days=120):
        """获取K线数据（实时模式，含预估成交量）"""
        today = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days*2)).strftime("%Y%m%d")
        
        try:
            # 下载历史数据到今天
            self.xtdata.download_history_data2(
                stock_list=[stock_code],
                period='1d',
                start_time=start_date,
                end_time=today
            )
            
            # 获取数据
            data = self.xtdata.get_market_data_ex(
                field_list=['time', 'open', 'high', 'low', 'close', 'volume'],
                stock_list=[stock_code],
                period='1d',
                start_time=start_date,
                end_time=today
            )
            
            if stock_code not in data or data[stock_code] is None:
                return None
            
            df = data[stock_code].copy()
            df['date'] = pd.to_datetime(df['time'], unit='ms')
            df = df.set_index('date').sort_index()
            df = df.tail(days)
            
            # 盘中更新实时价格和预估成交量
            now = datetime.now()
            if now.hour < 15:
                try:
                    full_tick = self.xtdata.get_full_tick([stock_code])
                    if stock_code in full_tick:
                        tick = full_tick[stock_code]
                        if len(df) > 0:
                            # 更新实时价格
                            df.loc[df.index[-1], 'close'] = tick.get('lastPrice', df['close'].iloc[-1])
                            # 预估全天成交量
                            current_volume = tick.get('volume', 0)
                            estimated_volume = self._estimate_full_day_volume(current_volume, now)
                            df.loc[df.index[-1], 'volume'] = int(estimated_volume)
                            print(f"  已更新盘中数据: 现价={tick.get('lastPrice')}, 预估全天成交量={int(estimated_volume)}")
                except Exception as e:
                    print(f"  获取实时数据失败: {e}")
            
            return df
        except Exception as e:
            print(f"获取K线数据失败: {e}")
            return None
    
    def _estimate_full_day_volume(self, current_volume, current_time):
        """预估全天成交量 - 基于A股成交量分布规律：开盘量 > 收盘量 > 盘中量"""
        hour = current_time.hour
        minute = current_time.minute
        
        # 计算当前时刻的累计成交量占比
        # 9:30-10:30 占35%，10:30-11:30 占20%，13:00-14:30 占30%，14:30-15:00 占15%
        
        if hour < 10 or (hour == 10 and minute < 30):
            # 9:30-10:30 开盘活跃期：35% / 60分钟 = 0.583% 每分钟
            total_minutes = (hour - 9) * 60 + minute - 30
            estimated_ratio = total_minutes * 0.00583
        elif hour < 11 or (hour == 11 and minute <= 30):
            # 10:30-11:30 上午平稳期：20% / 60分钟 = 0.333% 每分钟
            minutes_in_session = (hour - 10) * 60 + minute - 30
            estimated_ratio = 0.35 + minutes_in_session * 0.00333
        elif hour < 14 or (hour == 14 and minute < 30):
            # 13:00-14:30 下午平稳期：30% / 90分钟 = 0.333% 每分钟
            minutes_in_pm = (hour - 13) * 60 + minute
            estimated_ratio = 0.55 + minutes_in_pm * 0.00333
        else:
            # 14:30-15:00 尾盘冲刺期：15% / 30分钟 = 0.5% 每分钟
            minutes_in_close = (hour - 14) * 60 + minute - 30
            estimated_ratio = 0.85 + minutes_in_close * 0.005
        
        # 边界保护
        if estimated_ratio <= 0.01:
            estimated_ratio = 0.01
        if estimated_ratio > 1:
            estimated_ratio = 1.0
        
        return int(current_volume / estimated_ratio)
    
    def _calc_price_volume_score_realtime(self, df):
        """计算量价形态分（实时模式）"""
        if df is None or len(df) < 20:
            return {"score": 0, "details": {}, "description": "数据不足"}
        
        close = df['close']
        volume = df['volume']
        
        # 10日峰值用历史数据（排除今天）
        if len(df) >= 11:
            vol_10peak = volume.iloc[-11:-1].max()
            vol_10peak_date = volume.iloc[-11:-1].idxmax().strftime('%Y-%m-%d')
            price_10peak = close.iloc[-11:-1].max()
        else:
            vol_10peak = volume.tail(10).max()
            vol_10peak_date = volume.tail(10).idxmax().strftime('%Y-%m-%d')
            price_10peak = close.tail(10).max()
        
        # 当天成交量（已预估）
        current_vol = volume.iloc[-1]
        vol_ratio = current_vol / vol_10peak if vol_10peak > 0 else 1
        
        # 回撤
        drawdown = (close.iloc[-1] - price_10peak) / price_10peak if price_10peak > 0 else 0
        
        # MA20
        ma20 = close.rolling(20).mean()
        ma20_current = ma20.iloc[-1]
        ma20_slope = (ma20.iloc[-1] - ma20.iloc[-2]) / ma20.iloc[-2] if len(ma20) >= 2 and ma20.iloc[-2] != 0 else 0
        
        # 当日涨跌
        pct_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) >= 2 else 0
        is_declining = pct_change < 0
        
        # 评分逻辑（同父类）
        score = 0
        description = ""
        
        if vol_ratio < 0.30 and drawdown < -0.15 and ma20_slope > 0:
            score = 10
            description = "完美缩量回调：极度缩量(<30%)+深度回撤(>15%)+趋势向上"
        elif vol_ratio < 0.30 and drawdown < -0.10 and ma20_slope > 0:
            score = 9
            description = "优秀缩量回调：极度缩量(<30%)+较大回撤(>10%)+趋势向上"
        elif vol_ratio < 0.50 and drawdown < -0.10 and ma20_slope > 0:
            score = 8
            description = "理想缩量回调：缩量(<50%)+回撤>10%+趋势向上"
        elif vol_ratio < 0.50 and drawdown < -0.08 and ma20_slope > 0:
            score = 7
            description = "较好缩量回调：缩量(<50%)+回撤>8%+趋势向上"
        elif vol_ratio < 0.70 and drawdown < -0.05:
            score = 6
            description = "一般缩量回调：缩量(<70%)+小幅回撤(>5%)"
        elif vol_ratio < 0.70:
            score = 5
            description = "缩量状态(<70%)"
        elif vol_ratio <= 1.0:
            if is_declining:
                score = 4
                description = "缩量下跌，正常调整"
            else:
                score = 3
                description = "正常成交量"
        else:
            if pct_change > 0:
                score = 2
                description = "放量上涨，注意追高风险"
            else:
                score = 1
                description = "放量下跌，抛压沉重"
        
        return {
            "score": score,
            "signals": {
                "vol_ratio": round(vol_ratio, 2),
                "vol_10peak": int(vol_10peak),
                "vol_10peak_date": vol_10peak_date,
                "current_volume": int(current_vol),
                "drawdown_pct": round(drawdown * 100, 1),
                "price_10peak": round(price_10peak, 2),
                "current_price": round(close.iloc[-1], 2),
                "ma20": round(ma20_current, 2),
                "ma20_slope_pct": round(ma20_slope * 100, 2),
                "pct_change_pct": round(pct_change * 100, 2),
            },
            "description": description
        }


