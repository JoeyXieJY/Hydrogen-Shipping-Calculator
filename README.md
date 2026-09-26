# HySupply Shipping Calculator — 初学者版

这个版本使用 **Streamlit**。你不需要学习 HTML、CSS、JavaScript、API 或前后端框架。

项目只有几个关键文件：

```text
HySupply_Streamlit_Beginner/
├── app.py           # 网页界面：输入框、导航、结果卡片和图表
├── model.py         # Excel迁移后的计算公式
├── model_data.json  # 港口、航线和运输介质参数
├── test_model.py    # 计算检查
└── requirements.txt # 需要安装的Python库
```

## 第一次运行

打开此文件夹，在终端依次输入：

```bash
python -m venv .venv
```

Windows激活虚拟环境：

```bash
.venv\Scripts\activate
```

安装依赖：

```bash
python -m pip install -r requirements.txt
```

启动网页：

```bash
streamlit run app.py
```

浏览器通常会自动打开。如果没有打开，请访问：

```text
http://localhost:8501
```

## 以后如何启动

```bash
.venv\Scripts\activate
streamlit run app.py
```

停止网页：在终端按 `Ctrl + C`。

## 如何检查计算

```bash
python -m unittest test_model.py -v
```

## 用Codex修改时可以直接这样说

```text
请只修改 app.py，把输入栏宽度缩小，不要修改 model.py，并检查代码语法。
```

```text
请在 model.py 中增加距离敏感性分析，不要复制现有公式，修改后运行 test_model.py。
```

```text
请增加结果CSV下载按钮，保持当前页面布局和计算公式不变。
```

## 重要说明

- 附件工作簿中目前只有 Ammonia 与 Hydrogen 的关键参数和计算结果完整。
- LNG、Methanol、LOHC 没有在网页中生成虚构结果。
- 界面预览图里的数值仅用于设计展示；实际网页始终根据输入参数重新计算。
- `model.py` 复杂是因为它承载完整工程计算。初学阶段主要修改 `app.py` 即可。
