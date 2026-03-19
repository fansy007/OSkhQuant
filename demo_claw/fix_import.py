import os
path = r'E:\workspace\OSkhQuant\demo_claw\strategy\manual\buy_technique_strategy_manual.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 替换导入行
content = content.replace(
    "sys.path.insert(0, os.path.join(PROJECT_ROOT, 'strategy'))",
    "sys.path.insert(0, PROJECT_ROOT)"
)
content = content.replace(
    "from buy_scorer_manual import StockScorerManual",
    "from manual.buy_scorer_manual import StockScorerManual"
)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('done')
