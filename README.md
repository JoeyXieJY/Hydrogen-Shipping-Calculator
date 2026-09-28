# Hydrogen Shipping Cost Model

Streamlit模型，用于比较Gladstone（澳大利亚）至Tokyo（日本）的液氨和液氢海运成本、交付量与运输链温室气体排放。

## 模型边界

```text
Australian export terminal → ocean shipping → Japanese import terminal → ammonia cracking
```

模型明确排除制氢、制氨、上游原料生产以及船舶、储罐和终端建造的隐含碳。因此排放结果命名为`Transport-chain GHG emissions`，不是完整Well-to-Wake结果。

## 文件结构

```text
app.py             Streamlit界面
model.py           可独立测试的核心计算
model_data.json    默认参数、来源、范围和回归基准
test_model.py      24项回归与工程约束测试
STAGE2_CHANGES.md  修改记录及公式说明
requirements.txt   Python依赖
```

## 安装与运行

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

macOS或Linux：

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

浏览器访问`http://localhost:8501`。

## 测试

```bash
python -m pytest -q
python -m unittest test_model.py -v
python -m compileall .
```

## 主要输出

- Shipping cost：不含氨裂解成本，以理论氢当量为分母；
- Post-cracking landed hydrogen cost：包含裂解成本，以最终交付氢为分母；
- Delivered medium和Delivered H2；
- Transport-chain GHG emissions及各阶段分解；
- Supplementary hydrogen-leakage impact；
- NH3 slip；
- 单因素Low/Base/High敏感性分析和CSV下载；
- 参数来源、年份、类型和情景范围。

## 重要解释

- 路线固定为Gladstone–Tokyo，距离7148.72 km；不提供其他港口或自定义路线。
- 航速不是用户输入。模型内部使用20 knots作为参考航速，由距离自动计算航行时间，再乘`Voyage time adjustment factor`。
- BOG、储存损失和返航heel使用逐日指数计算。
- Heel是循环工作库存，只补充返航中的实际损失。
- `ship_capacity_kg`不再是独立输入；额定质量始终由舱容乘密度得到。
- 氨裂解基准综合产率为`0.177 × 0.99 × 0.75 = 0.1314225 kg H2/kg NH3`。
- 氢泄漏气候影响单独显示，默认不纳入监管型碳成本。
- 原工作簿中未能核实来源和基准年份的经济参数保留原值，并明确标记为`Legacy workbook value`。
- 所有敏感性范围都是情景范围，不是统计置信区间。

All results are estimates based on the selected assumptions.
