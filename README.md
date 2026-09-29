# Hydrogen Shipping Cost Model

独立的 Streamlit 应用，比较澳大利亚 Gladstone 至日本 Tokyo 固定航线（7,148.72 km）的氨与液氢运输链成本、交付量和排放。页面只有这一条路线；港口与距离不可切换。

## 运行环境

- Python 3.10 或更新版本
- `requirements.txt` 中的 Streamlit、pandas 和测试依赖

在仓库根目录运行：

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py --server.headless true --server.port 8501
```

macOS / Linux 可将最后两条命令改为 `.venv/bin/python -m pip install -r requirements.txt` 和 `.venv/bin/streamlit run app.py --server.headless true --server.port 8501`。打开 `http://localhost:8501`。部署 Streamlit 时将入口文件设为仓库根目录的 `app.py`；`model.py`、`model_data.json` 和 `presentation.py` 必须与入口文件一起部署。

## 验证

在已安装依赖的 Python 环境中运行：

```powershell
python -c "from model import kg_year_to_kt_year, kg_year_to_t_year; print(kg_year_to_kt_year(1000000), kg_year_to_t_year(1000))"
python -c "import model"
python -c "import presentation"
python -m compileall -q .
python -m pytest -q
python -m unittest test_model.py -v
```

`test_app.py` 使用 Streamlit AppTest 检查默认页面。真实启动后可请求 `http://localhost:8501/_stcore/health`，期望 HTTP 200。

## 模型与输出

模型边界为澳大利亚出口码头、海运、日本进口码头，以及氨路线的裂解。排放结果是 **transport-chain emissions**；制氢、制氨和设备建造排放不在计算范围内，因此不是完整的 Well-to-Wake 核算。氢泄漏的间接气候影响单独显示，默认不计入碳成本。

默认每年运行 350 天；氨理论氢质量换算为 0.177 kg H2/kg NH3，裂解转化率 99%，PSA 回收率 75%，裂解成本 0.35 USD/kg H2。单程航行时间由 7,148.72 km 与模型中的参考航速自动计算，并可用 `Voyage time adjustment factor` 调整。BOG 与储罐停留损耗按逐日指数计算；fill fraction 与 heel 进入每航次质量平衡。

页面分别展示 shipping cost 和 **Delivered transport-chain cost (A$/kg H2)**。两者是并列比较值，交付成本已包含运费，不能再次相加。默认成本约为：

| Carrier | Shipping cost (A$/kg H2-eq) | Delivered transport-chain cost (A$/kg H2) |
| --- | ---: | ---: |
| Ammonia | 0.355 | 0.978 |
| Hydrogen | 0.792 | 0.792 |

氨路线默认可用运输介质约 1,854.93 kt/year，交付氢约 243.78 kt/year；主表使用 t/year，约 243,780.14 t/year。顶部最低交付成本为 Hydrogen，约 A$0.79/kg H2。

页面还提供单因素敏感性分析、参数来源与年份及情景范围、CSV 下载和 Mass-balance audit。来源记录没有完整出处时标记为 `Full citation to be verified`；这些区间是输入情景，不是统计置信区间。

## 文件

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit 页面 |
| `model.py` | 可独立导入的计算与单位换算 |
| `presentation.py` | 显示标签、表格与指标卡数据 |
| `model_data.json` | 固定路线、默认参数、来源和回归基准 |
| `test_model.py` | 模型与显示数据回归测试 |
| `test_app.py` | Streamlit AppTest |
| `requirements.txt` | 部署及测试依赖 |

All results are estimates based on the selected assumptions.
