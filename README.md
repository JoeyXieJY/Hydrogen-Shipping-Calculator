# Hydrogen Shipping Cost Model

This Streamlit app compares the costs, delivery volumes, and emissions of transporting hydrogen as ammonia or liquid hydrogen from Gladstone, Australia, to Tokyo, Japan. It uses a fixed one-way distance of 7,148.72 km. The route, ports, and distance cannot be changed in the app.

## Model scope

The model covers the Australian export terminal, ocean transport, the Japanese import terminal, and ammonia cracking for the ammonia pathway. It excludes hydrogen and ammonia production and emissions from equipment construction. The emissions results therefore represent the transport chain, not a full Well-to-Wake assessment.

The indirect climate impact of hydrogen leakage is reported separately and is excluded from carbon costs by default.

One-way voyage time is calculated from the route distance and the model's reference vessel speed. The `Voyage time adjustment factor` allows users to account for longer voyages. Boil-off gas (BOG) and storage losses are calculated using daily compounded loss rates. The loading fraction and heel, the cargo retained in the tank, are included in the mass balance for each voyage.

Key default assumptions are:

| Parameter | Default value |
| --- | ---: |
| Operating days per year | 350 |
| Theoretical hydrogen content of ammonia | 0.177 kg H2/kg NH3 |
| Ammonia cracker conversion | 99% |
| Pressure swing adsorption (PSA) recovery | 75% |
| Ammonia cracking cost | 0.35 USD/kg H2 |

## Reading the results

The app reports shipping cost and delivered transport-chain cost separately. Delivered cost already includes shipping, so the two values should not be added together. The default results are approximately:

| Carrier | Shipping cost (A$/kg H2-eq) | Delivered transport-chain cost (A$/kg H2) |
| --- | ---: | ---: |
| Ammonia | 0.355 | 0.978 |
| Hydrogen | 0.792 | 0.792 |

Under these assumptions, liquid hydrogen has the lower delivered transport-chain cost, at about A$0.79/kg H2. These costs exclude hydrogen and ammonia production.

For the ammonia pathway, the default usable transported medium is about 1,854.93 kt/year, and delivered hydrogen is about 243.78 kt/year. The main results table reports delivery in tonnes per year: approximately 243,780.14 t/year.

The app also provides one-at-a-time sensitivity analysis, parameter sources and years, scenario ranges, CSV downloads, and a mass-balance audit. Incomplete references are marked `Full citation to be verified`. The parameter ranges describe input scenarios; they are not statistical confidence intervals.

All results are estimates based on the selected assumptions.

## Running locally

Use Python 3.10 or later. The required packages, including Streamlit, pandas, and the test dependencies, are listed in `requirements.txt`.

Run the following commands from the repository's root directory.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\streamlit.exe run app.py --server.headless true --server.port 8501
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/streamlit run app.py --server.headless true --server.port 8501
```

Open `http://localhost:8501` in your browser.

## Tests and checks

Run these checks in the Python environment where the dependencies are installed. If you used the virtual environment above, replace `python` with `.\.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux.

```bash
python -c "from model import kg_year_to_kt_year, kg_year_to_t_year; print(kg_year_to_kt_year(1000000), kg_year_to_t_year(1000))"
python -c "import model"
python -c "import presentation"
python -m compileall -q .
python -m pytest -q
python -m unittest test_model.py -v
```

The unit-conversion check should print `1.0 1.0`. `test_app.py` uses Streamlit AppTest to check the default page. With the app running, a request to `http://localhost:8501/_stcore/health` should return HTTP 200.

## Deployment

Set the Streamlit entry point to `app.py` in the repository's root directory. Include `model.py`, `model_data.json`, and `presentation.py` alongside it, together with `requirements.txt`.

## Repository files

| File | Purpose |
| --- | --- |
| `app.py` | Streamlit interface |
| `model.py` | Model calculations and unit conversions; can be imported independently of the app |
| `presentation.py` | Display labels, tables, and metric-card data |
| `model_data.json` | Fixed route, default parameters, sources, and regression baselines |
| `test_model.py` | Regression tests for calculations and display data |
| `test_app.py` | Interface tests using Streamlit AppTest |
| `requirements.txt` | Dependencies for deployment and testing |
