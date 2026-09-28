# 在 Codex 中继续实现和修改

## 1. 把整个文件夹交给 Codex

在 Codex 中打开 `HySupply_Streamlit_Beginner` 文件夹。第一次可以这样说：

```text
请先阅读 README.md、app.py、model.py 和 test_model.py。
这是一个面向Python初学者的Streamlit项目。
所有网页修改放在app.py，所有工程计算放在model.py，参数及来源放在model_data.json。
修改后必须运行：python -m pytest -q
不要增加React、Flask、JavaScript或数据库。
```

## 2. 让 Codex 修改页面

```text
请修改 app.py：保留顶部名称、左侧输入和右侧结果区。
页面保持白色背景和绿色主题，不要增加新的页面或复杂功能。
完成后检查Python语法，不要修改model.py。
```

## 3. 让 Codex 修改模型

修改公式时，要把 Excel 单元格和公式说明清楚。例如：

```text
请修改model.py中的碳成本计算。
新公式为：annual carbon emissions × carbon price ÷ 1,000,000。
保持calculate_case的输入和输出格式不变，并在test_model.py中增加测试。
```

## 4. 让 Codex 增加功能

```text
请在app.py增加“Download results as CSV”按钮。
CSV包含carrier、annual cost、delivered quantity和AUD/kg H2。
不要修改计算公式，不要增加新依赖。
```

## 5. 每次修改后的检查

要求 Codex 运行：

```bash
python -m compileall .
python -m pytest -q
python -m unittest test_model.py -v
```

如果修改了网页，自己再运行：

```bash
python -m streamlit run app.py
```

然后在浏览器中检查：

- 输入框是否完整；
- 点击 Calculate 后数字是否更新；
- 成本、排放和敏感性图表是否显示；
- 页面在缩小浏览器窗口后是否仍能使用；
- 不应出现红色错误提示。

## 6. 初学阶段不要让 Codex 添加的内容

- React、Vue 或 Node.js；
- Flask/FastAPI 前后端分离；
- JavaScript 图表库；
- 用户登录；
- 数据库；
- Docker 或云端部署配置。

这些功能并非不能做，而是会显著增加你理解和维护项目的难度。
