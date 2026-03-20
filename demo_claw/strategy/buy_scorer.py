# -*- coding: utf-8 -*-
"""
StockScorer - 内嵌到strategy目录的评分器

Usage:
    from strategy.buy_scorer import StockScorer
    scorer = StockScorer(price_volume_weight=0.6, fundamental_weight=0.4, xtdata=xtdata)
    result = scorer.score("600519.SH", date="20250317")
"""
import sys
import os
import importlib.util
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# 加载配置文件
def _load_config():
    """从配置文件加载参数"""
    config = {}
    config_path = os.path.join(os.path.dirname(__file__), 'buy_technique_strategy.config')
    if os.path.exists(config_path):
        with open(config_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                if ',' in line:
                    key, value = line.split(',', 1)
                    config[key.strip()] = value.strip()
    return config

# 全局配置
_CONFIG = _load_config()

# 禁用打印（回测时不输出详细信息）
_print = print
print = lambda *args, **kwargs: None


class StockScorer:
    """股票评分器 - 用于回测"""

    def __init__(self, price_volume_weight=0.6, fundamental_weight=0.4, xtdata=None, ma_period=None):
        """
        初始化评分器

        Args:
            price_volume_weight: 量价形态权重，默认0.6
            fundamental_weight: 基本面权重，默认0.4
            xtdata: xtquant数据对象（必传）
            ma_period: 均线周期，默认从配置读取（如配置为空则默认20）
        """
        if abs(price_volume_weight + fundamental_weight - 1.0) > 0.001:
            raise ValueError(f"权重之和必须等于1，当前：{price_volume_weight + fundamental_weight}")

        self.pv_weight = price_volume_weight
        self.fund_weight = fundamental_weight

        # 均线周期：从配置读取或使用默认值
        if ma_period is not None:
            self.ma_period = ma_period
        else:
            self.ma_period = int(_CONFIG.get('ma_period', 20))

        if xtdata is not None:
            self.xtdata = xtdata
            self.xtquant = None
        else:
            raise ValueError("xtdata 不能为空")

    def preload_data(self, stock_list: list, date: str, kline_days: int = 120):
        """
        批量预下载所有股票的数据（K线 + 财务）

        Args:
            stock_list: 股票列表
            date: 日期
            kline_days: K线天数
        """
        # 1. 批量下载财务数据（一次）
        # try:
        #     self.xtdata.download_financial_data2(
        #         stock_list=stock_list,
        #         table_list=['Income', 'CashFlow']
        #     )
        # except:
        #     pass

        # 2. 批量下载K线数据（一次）
        start_year = int(date[:4])
        start_month = int(date[4:6])
        start_day = int(date[6:8])
        import datetime
        report_dt = datetime.datetime(start_year, start_month, start_day)
        start_dt = report_dt - datetime.timedelta(days=kline_days)
        start_time = start_dt.strftime('%Y%m%d')

        # try:
        #     self.xtdata.download_history_data2(
        #         stock_list=stock_list,
        #         period='1d',
        #         start_time=start_time,
        #         end_time=date
        #     )
        # except:
        #     pass

    def score(self, stock_code, date):
        """
        对股票进行评分（回测用）

        Args:
            stock_code: 股票代码，如 "600519.SH"
            date: 日期，格式 "YYYYMMDD"

        Returns:
            dict: 评分结果
        """
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

        return result

    def _get_kline(self, stock_code, date, days=120):
        """获取K线数据（回测用，已在preload中批量下载）"""
        start_date = (datetime.strptime(date, "%Y%m%d") - timedelta(days=days*2)).strftime("%Y%m%d")

        try:
            # 直接从本地获取（已批量下载）
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

    def _get_financial(self, stock_code, date):
        """获取财务数据 - 从本地读取（已在preload中批量下载）"""
        try:
            # 直接从本地获取财务数据（已批量下载）
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

            # 解析Income表
            income_df = tables.get('Income', pd.DataFrame())
            if income_df.empty:
                return None

            # 确定日期列名
            date_col = 'endDate' if 'endDate' in income_df.columns else 'm_timetag'
            if date_col not in income_df.columns:
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
                return None

            # 确定目标年报日期
            report_date = self._get_latest_report_date(date, available_dates)

            # 获取本期数据
            current = income_df[income_df['parsed_date'] == report_date]
            if current.empty:
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

        # MA（可配置周期）
        ma = close.rolling(self.ma_period).mean()
        ma_current = ma.iloc[-1]
        ma_slope = (ma.iloc[-1] - ma.iloc[-2]) / ma.iloc[-2] if len(ma) >= 2 and ma.iloc[-2] != 0 else 0

        # 当日涨跌
        pct_change = (close.iloc[-1] - close.iloc[-2]) / close.iloc[-2] if len(close) >= 2 else 0
        is_declining = pct_change < 0

        # 评分逻辑
        score = 0
        description = ""

        if vol_ratio < 0.40 and (-0.15 < drawdown < -0.10) and ma_slope > 0:
            score = 10
            description = "完美缩量回调"
        elif vol_ratio < 0.50 and (-0.15 < drawdown < -0.08) and ma_slope > 0:
            score = 9
            description = "优秀缩量回调"
        elif vol_ratio < 0.60 and (-0.15 < drawdown < -0.08) and ma_slope > 0:
            score = 8
            description = "理想缩量回调"
        elif vol_ratio < 0.60 and drawdown < -0.06 and ma_slope > 0:
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
                "vol_10peak_date": vol_10peak_date,
                "current_volume": int(current_vol),
                "drawdown_pct": round(drawdown * 100, 1),
                "price_10peak": round(price_10peak, 2),
                "current_price": round(close.iloc[-1], 2),
                "ma": round(ma_current, 2),
                "ma_period": self.ma_period,
                "ma_slope_pct": round(ma_slope * 100, 2),
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
