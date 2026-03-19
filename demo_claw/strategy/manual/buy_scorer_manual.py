# -*- coding: utf-8 -*-
"""
StockScorer Manual - 支持回测和实时评分的评分器

Usage:
    # 回测
    scorer = StockScorerManual(price_volume_weight=0.6, fundamental_weight=0.4, xtdata=xtdata)
    result = scorer.score("600519.SH", date="20250317")

    # 实时（不传date或传None）
    scorer = StockScorerManual(price_volume_weight=0.6, fundamental_weight=0.4, xtdata=xtdata)
    result = scorer.score("600519.SH")  # 使用今天实时数据
"""
import sys
import os
import importlib.util
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


class StockScorerManual:
    """股票评分器 - 支持回测和实时"""

    def __init__(self, price_volume_weight=0.6, fundamental_weight=0.4, xtdata=None):
        """
        初始化评分器

        Args:
            price_volume_weight: 量价形态权重，默认0.6
            fundamental_weight: 基本面权重，默认0.4
            xtdata: xtquant数据对象（必传）
        """
        if abs(price_volume_weight + fundamental_weight - 1.0) > 0.001:
            raise ValueError(f"权重之和必须等于1，当前：{price_volume_weight + fundamental_weight}")

        self.pv_weight = price_volume_weight
        self.fund_weight = fundamental_weight

        if xtdata is not None:
            self.xtdata = xtdata
            self.xtquant = None
        else:
            raise ValueError("xtdata 不能为空")

    def preload_data(self, stock_list: list, date: str = None, kline_days: int = 120):
        """
        批量预下载所有股票的数据（K线 + 财务）

        Args:
            stock_list: 股票列表
            date: 日期（可选，不传则使用今天实时数据）
            kline_days: K线天数
        """
        # 如果没有传date，使用今天
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        # 1. 批量下载财务数据（一次）
        try:
            self.xtdata.download_financial_data2(
                stock_list=stock_list,
                table_list=['Income', 'CashFlow']
            )
        except:
            pass

        # 2. 批量下载K线数据（一次）
        start_year = int(date[:4])
        start_month = int(date[4:6])
        start_day = int(date[6:8])
        report_dt = datetime(start_year, start_month, start_day)
        start_dt = report_dt - timedelta(days=kline_days)
        start_time = start_dt.strftime('%Y%m%d')

        try:
            self.xtdata.download_history_data2(
                stock_list=stock_list,
                period='1d',
                start_time=start_time,
                end_time=date
            )
        except:
            pass

    def score(self, stock_code, date=None):
        """
        对股票进行评分

        Args:
            stock_code: 股票代码，如 "600519.SH"
            date: 日期（可选，不传或传None则使用实时模式）

        Returns:
            dict: 评分结果
        """
        # 如果没有传date，使用实时模式
        if date is None:
            return self._score_realtime(stock_code)
        else:
            return self._score_backtest(stock_code, date)

    def _score_backtest(self, stock_code, date):
        """回测模式评分"""
        # 1. 获取K线数据
        kline_df = self._get_kline(stock_code, date)
        fin_data = self._get_financial(stock_code, date)

        # 2. 计算各维度分数
        pv_result = self._calc_price_volume_score(kline_df, is_realtime=False)
        fund_result = self._calc_fundamental_score(fin_data)

        # 3. 计算综合分
        composite = pv_result["score"] * self.pv_weight + fund_result["score"] * self.fund_weight

        # 4. 建议
        recommendation = self._get_recommendation(composite)

        result = {
            "code": stock_code,
            "date": date,
            "mode": "backtest",
            "composite_score": round(composite, 1),
            "price_volume_score": pv_result["score"],
            "fundamental_score": fund_result["score"],
            "recommendation": recommendation,
            "details": {
                "price_volume": pv_result,
                "fundamental": fund_result
            }
        }

        return result

    def _score_realtime(self, stock_code):
        """实时模式评分"""
        today = datetime.now().strftime("%Y%m%d")

        # 1. 获取K线数据（含实时更新）
        kline_df = self._get_kline_realtime(stock_code)
        fin_data = self._get_financial(stock_code, today)

        # 2. 计算各维度分数
        pv_result = self._calc_price_volume_score(kline_df, is_realtime=True)
        fund_result = self._calc_fundamental_score(fin_data)

        # 3. 计算综合分
        composite = pv_result["score"] * self.pv_weight + fund_result["score"] * self.fund_weight

        # 4. 建议
        recommendation = self._get_recommendation(composite)

        result = {
            "code": stock_code,
            "date": today,
            "mode": "realtime",
            "composite_score": round(composite, 1),
            "price_volume_score": pv_result["score"],
            "fundamental_score": fund_result["score"],
            "recommendation": recommendation,
            "details": {
                "price_volume": pv_result,
                "fundamental": fund_result
            }
        }

        return result

    def _get_recommendation(self, composite):
        """根据综合分返回建议"""
        if composite >= 8.0:
            return "强烈买入"
        elif composite >= 7.0:
            return "正常买入"
        elif composite >= 6.0:
            return "轻仓试错"
        elif composite >= 4.0:
            return "中性观望"
        else:
            return "不买入"

    def _get_kline(self, stock_code, date, days=120):
        """获取K线数据（回测用）"""
        start_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")

        try:
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
        except:
            return None

    def _get_kline_realtime(self, stock_code, days=120):
        """获取K线数据（实时模式，含预估成交量）"""
        today = datetime.now().strftime("%Y%m%d")
        start_date = (datetime.now() - timedelta(days=days*2)).strftime("%Y%m%d")

        try:
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
            if now.hour < 15:  # 如果在交易时间段
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
                except:
                    pass

            return df
        except:
            return None

    def _estimate_full_day_volume(self, current_volume, current_time):
        """预估全天成交量"""
        hour = current_time.hour
        minute = current_time.minute

        if hour < 10 or (hour == 10 and minute < 30):
            total_minutes = (hour - 9) * 60 + minute - 30
            estimated_ratio = total_minutes * 0.00583
        elif hour < 11 or (hour == 11 and minute <= 30):
            minutes_in_session = (hour - 10) * 60 + minute - 30
            estimated_ratio = 0.35 + minutes_in_session * 0.00333
        elif hour < 14 or (hour == 14 and minute < 30):
            minutes_in_pm = (hour - 13) * 60 + minute
            estimated_ratio = 0.55 + minutes_in_pm * 0.00333
        else:
            minutes_in_close = (hour - 14) * 60 + minute - 30
            estimated_ratio = 0.85 + minutes_in_close * 0.005

        if estimated_ratio <= 0.01:
            estimated_ratio = 0.01
        if estimated_ratio > 1:
            estimated_ratio = 1.0

        return int(current_volume / estimated_ratio)

    def _get_financial(self, stock_code, date):
        """获取财务数据 - 从本地读取"""
        try:
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
                return None

            tables = result[stock_code]

            income_df = tables.get('Income', pd.DataFrame())
            if income_df.empty:
                return None

            date_col = 'endDate' if 'endDate' in income_df.columns else 'm_timetag'
            if date_col not in income_df.columns:
                return None

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

            available_dates = income_df['parsed_date'].dropna().unique()
            available_dates = sorted([d for d in available_dates if d is not None], reverse=True)
            if not available_dates:
                return None

            report_date = self._get_latest_report_date(date, available_dates)

            current = income_df[income_df['parsed_date'] == report_date]
            if current.empty:
                return None

            revenue = current['revenue'].iloc[0] if 'revenue' in current.columns else 0
            net_profit_deducted = current['net_profit_incl_min_int_inc_after'].iloc[0] if 'net_profit_incl_min_int_inc_after' in current.columns else 0

            if pd.isna(revenue):
                revenue = 0
            if pd.isna(net_profit_deducted):
                net_profit_deducted = 0

            last_year_date = f"{int(report_date[:4])-1}1231"
            last_year = income_df[income_df['parsed_date'] == last_year_date]

            revenue_last = last_year['revenue'].iloc[0] if not last_year.empty and 'revenue' in last_year.columns else 0
            net_profit_deducted_last = last_year['net_profit_incl_min_int_inc_after'].iloc[0] if not last_year.empty and 'net_profit_incl_min_int_inc_after' in last_year.columns else 0

            if pd.isna(revenue_last):
                revenue_last = 0
            if pd.isna(net_profit_deducted_last):
                net_profit_deducted_last = 0

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

            return {
                "revenue": float(revenue) if revenue else 0,
                "revenue_last": float(revenue_last) if revenue_last else 0,
                "net_profit_deducted": float(net_profit_deducted) if net_profit_deducted else 0,
                "net_profit_deducted_last": float(net_profit_deducted_last) if net_profit_deducted_last else 0,
                "operating_cash_flow": float(operating_cash_flow) if operating_cash_flow else 0,
                "report_date": report_date
            }
        except:
            return None

    def _get_latest_report_date(self, check_date, available_dates=None):
        """返回最新可用的年报日期"""
        year = int(check_date[:4])
        target_year = year - 1
        target_date = f"{target_year}1231"

        if available_dates:
            annual_reports = sorted([d for d in available_dates if d.endswith('1231')], reverse=True)
            for d in annual_reports:
                if d.startswith(str(target_year)):
                    return d
            for d in annual_reports:
                if d.startswith(str(target_year - 1)):
                    return d
            if annual_reports:
                return annual_reports[0]

        return target_date

    def _calc_price_volume_score(self, df, is_realtime=False):
        """计算量价形态分"""
        if df is None or len(df) < 20:
            return {"score": 0, "details": {}, "description": "数据不足"}

        close = df['close']
        volume = df['volume']

        # 实时模式用不含今天的数据，回测模式用全部数据
        if is_realtime and len(df) >= 11:
            vol_10peak = volume.iloc[-11:-1].max()
            vol_10peak_date = volume.iloc[-11:-1].idxmax().strftime('%Y-%m-%d')
            price_10peak = close.iloc[-11:-1].max()
        else:
            vol_10peak = volume.tail(10).max()
            vol_10peak_date = volume.tail(10).idxmax().strftime('%Y-%m-%d')
            price_10peak = close.tail(10).max()

        current_vol = volume.iloc[-1]
        vol_ratio = current_vol / vol_10peak if vol_10peak > 0 else 1

        drawdown = (close.iloc[-1] - price_10peak) / price_10peak if price_10peak > 0 else 0

        ma20 = close.rolling(20).mean()
        ma20_current = ma20.iloc[-1]
        ma20_slope = (ma20.iloc[-1] - ma20.iloc[-2]) / ma20.iloc[-2] if len(ma20) >= 2 and ma20.iloc[-2] != 0 else 0

        pct_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) >= 2 else 0
        is_declining = pct_change < 0

        score = 0
        description = ""

        if vol_ratio < 0.40 and (-0.15 < drawdown < -0.10) and ma20_slope > 0:
            score = 10
            description = "完美缩量回调"
        elif vol_ratio < 0.50 and (-0.15 < drawdown < -0.08) and ma20_slope > 0:
            score = 9
            description = "优秀缩量回调"
        elif vol_ratio < 0.60 and (-0.15 < drawdown < -0.08) and ma20_slope > 0:
            score = 8
            description = "理想缩量回调"
        elif vol_ratio < 0.60 and drawdown < -0.06 and ma20_slope > 0:
            score = 7
            description = "较好缩量回调"
        elif vol_ratio < 0.70 and drawdown < -0.05:
            score = 5
            description = "一般缩量回调"
        elif vol_ratio <= 1.0:
            if is_declining:
                score = 3
                description = "缩量下跌"
            else:
                score = 3
                description = "正常成交量"
        else:
            if pct_change > 0:
                score = 2
                description = "放量上涨"
            else:
                score = 1
                description = "放量下跌"

        return {
            "score": score,
            "signals": {
                "vol_ratio": round(vol_ratio, 2),
                "vol_10peak": int(vol_10peak),
                "current_volume": int(current_vol),
                "drawdown_pct": round(drawdown * 100, 1),
                "current_price": round(close.iloc[-1], 2),
                "ma20": round(ma20_current, 2),
                "ma20_slope_pct": round(ma20_slope * 100, 2),
            },
            "description": description
        }

    def _calc_fundamental_score(self, fin_data):
        """计算基本面分"""
        if fin_data is None:
            return {"score": 5, "details": {}, "description": "财务数据缺失"}

        revenue = fin_data.get("revenue", 0)
        revenue_last = fin_data.get("revenue_last", 0)
        profit = fin_data.get("net_profit_deducted", 0)
        profit_last = fin_data.get("net_profit_deducted_last", 0)
        cash_flow = fin_data.get("operating_cash_flow", 0)

        if revenue_last <= 0:
            revenue_last = revenue if revenue > 0 else 1
        if profit_last <= 0:
            profit_last = profit if profit > 0 else 1

        revenue_growth = (revenue - revenue_last) / revenue_last
        profit_growth = (profit - profit_last) / profit_last

        cash_flow_positive = cash_flow > 0
        revenue_growing = revenue_growth > 0
        profit_growing = profit_growth > 0
        both_growing = revenue_growing and profit_growing

        score = 0
        description = ""

        if not cash_flow_positive:
            if both_growing and revenue_growth > 0.20 and profit_growth > 0.20:
                score = 6
                description = "双增长>20%但现金流为负"
            elif both_growing:
                score = 4
                description = "双增长但现金流为负"
            else:
                score = 1
                description = "现金流为负且增长乏力"
        else:
            if both_growing and revenue_growth > 0.20 and profit_growth > 0.20:
                score = 10
                description = "优秀：双增长>20%"
            elif both_growing and revenue_growth > 0.20:
                score = 9
                description = "营收增长>20%"
            elif both_growing and profit_growth > 0.20:
                score = 9
                description = "扣非净利增长>20%"
            elif both_growing:
                if revenue_growth > 0.15 and profit_growth > 0.15:
                    score = 8
                    description = "双增长，增速较高"
                else:
                    score = 7
                    description = "双增长5-20%"
            elif revenue_growing or profit_growing:
                if revenue_growing:
                    score = 6
                    description = "营收增长，净利下滑"
                else:
                    score = 5
                    description = "净利增长，营收下滑"
            elif revenue_growth > -0.01 and revenue_growth < 0.05 and profit_growth > -0.01 and profit_growth < 0.05:
                score = 4
                description = "低个位数增长或持平"
            else:
                score = 2
                description = "营收或净利下滑"

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
                "report_date": fin_data.get("report_date", "")
            },
            "description": description
        }

    def print_report(self, result):
        """打印评分报告"""
        print(f"\n{'='*60}")
        print(f"股票: {result['code']}")
        print(f"日期: {result['date']} ({result['mode']})")
        print(f"{'='*60}")

        print(f"\n【综合分】{result['composite_score']}")
        print(f"  - 量价形态分: {result['price_volume_score']} (权重 {self.pv_weight})")
        print(f"  - 基本面分: {result['fundamental_score']} (权重 {self.fund_weight})")
        print(f"  - 建议: {result['recommendation']}")

        pv = result['details']['price_volume']
        print(f"\n【量价形态详情】")
        print(f"  得分: {pv['score']}/10")
        print(f"  描述: {pv['description']}")
        if 'signals' in pv:
            sig = pv['signals']
            print(f"  当前价: {sig.get('current_price', 'N/A')}")
            print(f"  成交量比: {sig.get('vol_ratio', 'N/A')}")
            print(f"  回撤: {sig.get('drawdown_pct', 'N/A')}%")
            print(f"  MA20: {sig.get('ma20', 'N/A')}")

        fund = result['details']['fundamental']
        print(f"\n【基本面详情】")
        print(f"  得分: {fund['score']}/10")
        print(f"  描述: {fund['description']}")
        if 'signals' in fund and fund['signals']:
            sig = fund['signals']
            print(f"  营收: {sig.get('revenue', 'N/A'):.2f}亿 (增速: {sig.get('revenue_growth_pct', 'N/A')}%)")
            print(f"  扣非净利: {sig.get('profit_deducted', 'N/A'):.2f}亿 (增速: {sig.get('profit_growth_pct', 'N/A')}%)")
            print(f"  经营现金流: {sig.get('operating_cash_flow', 'N/A'):.2f}亿")

        print(f"\n{'='*60}\n")


# 测试
if __name__ == '__main__':
    import os
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    XTQUANT_PATH = os.path.join(PROJECT_ROOT, '..', 'xtquant')

    # 加载xtquant
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

    scorer = StockScorerManual(price_volume_weight=0.6, fundamental_weight=0.4, xtdata=xtdata)

    # 测试回测模式
    print("=== 回测模式测试 ===")
    result1 = scorer.score("300797.SZ", date="20250317")
    scorer.print_report(result1)

    # 测试实时模式
    print("\n=== 实时模式测试 ===")
    result2 = scorer.score("300797.SZ")  # 不传date
    scorer.print_report(result2)
