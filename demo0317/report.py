# -*- coding: utf-8 -*-
"""
可视化报告模块
生成每日收益率对比图表
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
matplotlib.rcParams['axes.unicode_minus'] = False

OUTPUT_DIR = r'e:\workspace\OSkhQuant\demo0317'


def generate_report(csv_path: str = None, output_path: str = None):
    """生成可视化报告

    Args:
        csv_path: 每日资产CSV路径
        output_path: 输出图片路径
    """
    if csv_path is None:
        csv_path = os.path.join(OUTPUT_DIR, 'backtest_assets.csv')
    if output_path is None:
        output_path = os.path.join(OUTPUT_DIR, 'backtest_report.png')

    # 读取数据
    df = pd.read_csv(csv_path)
    print(f"读取数据: {len(df)} 行")

    # 计算每日收益率
    df['strategy_return'] = df['total_value'].pct_change() * 100  # 策略每日收益率%
    df['benchmark_return'] = df['benchmark_value'].pct_change() * 100  # 基准每日收益率%

    # 累计收益率
    df['strategy_cum_return'] = (df['total_value'] / df['total_value'].iloc[0] - 1) * 100
    df['benchmark_cum_return'] = (df['benchmark_value'] / df['benchmark_value'].iloc[0] - 1) * 100

    # 创建图表
    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle('回测报告 - 每日收益率对比', fontsize=14, fontweight='bold')

    # 1. 累计收益率对比
    ax1 = axes[0, 0]
    ax1.plot(df['date'], df['strategy_cum_return'], label='策略', linewidth=1.5, color='blue')
    ax1.plot(df['date'], df['benchmark_cum_return'], label='基准(中证500)', linewidth=1.5, color='orange')
    ax1.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax1.set_title('累计收益率对比')
    ax1.set_xlabel('日期')
    ax1.set_ylabel('收益率 (%)')
    ax1.legend()
    ax1.grid(True, alpha=0.3)
    # 减少x轴标签
    tick_positions = range(0, len(df), max(1, len(df) // 10))
    ax1.set_xticks([df['date'].iloc[i] for i in tick_positions])
    ax1.tick_params(axis='x', rotation=45)

    # 2. 每日收益率对比
    ax2 = axes[0, 1]
    ax2.bar(range(len(df)), df['strategy_return'], alpha=0.6, label='策略', color='blue', width=1)
    ax2.bar(range(len(df)), df['benchmark_return'], alpha=0.6, label='基准', color='orange', width=0.8)
    ax2.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax2.set_title('每日收益率')
    ax2.set_xlabel('交易日')
    ax2.set_ylabel('收益率 (%)')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. 胜率统计 - 策略 vs 基准
    ax3 = axes[1, 0]
    strategy_wins = (df['strategy_return'] > df['benchmark_return']).sum()
    total_days = len(df) - 1  # 排除第一天
    benchmark_wins = total_days - strategy_wins
    colors = ['#2ecc71', '#e74c3c']
    ax3.pie([strategy_wins, benchmark_wins], labels=['策略胜', '基准胜'],
            autopct='%1.1f%%', colors=colors, startangle=90)
    ax3.set_title(f'每日收益胜率对比 (共{total_days}天)')

    # 4. 收益分布
    ax4 = axes[1, 1]
    diff = df['strategy_return'].dropna()
    colors = ['green' if x > 0 else 'red' for x in diff]
    ax4.bar(range(len(diff)), diff, color=colors, alpha=0.7)
    ax4.axhline(y=0, color='gray', linestyle='--', alpha=0.5)
    ax4.set_title('策略每日超额收益 (策略 - 基准)')
    ax4.set_xlabel('交易日')
    ax4.set_ylabel('超额收益 (%)')
    ax4.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches='tight')
    print(f"图表已保存: {output_path}")

    # 打印统计
    print("\n========== 收益统计 ==========")
    print(f"总交易日: {len(df)}")
    print(f"策略总收益: {df['strategy_cum_return'].iloc[-1]:.2f}%")
    print(f"基准总收益: {df['benchmark_cum_return'].iloc[-1]:.2f}%")
    print(f"超额收益: {df['strategy_cum_return'].iloc[-1] - df['benchmark_cum_return'].iloc[-1]:.2f}%")
    print(f"策略胜率: {strategy_wins}/{total_days} = {strategy_wins/total_days*100:.1f}%")
    print(f"策略平均日收益: {df['strategy_return'].mean():.2f}%")
    print(f"策略最大日收益: {df['strategy_return'].max():.2f}%")
    print(f"策略最小日收益: {df['strategy_return'].min():.2f}%")

    return df


if __name__ == '__main__':
    generate_report()
