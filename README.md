# 🚜 Equipment Fleet Optimiser

A Streamlit web application for optimal assignment of construction equipment
across multiple sites over a planning horizon using **CP-SAT** (OR-Tools).
Minimises total cost: rental + relocation + unmet demand penalties.

[![Python](https://img.shields.io/badge/Python-3.9%2B-blue)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red)](https://streamlit.io)
[![OR-Tools](https://img.shields.io/badge/OR--Tools-CP--SAT-green)](https://developers.google.com/optimization)
[![License](https://img.shields.io/badge/License-MIT-lightgrey)](LICENSE)

---

## Quick start

```bash
git clone https://github.com/inigmat/equilibrium.fleet.git
cd equilibrium.fleet
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

## Project structure

```
equilibrium.fleet/
├── app.py           — Streamlit entry point
├── solver.py        — CP-SAT model + greedy baseline
├── data_gen.py      — Realistic scenario generator
├── charts.py        — Plotly visualisations
├── requirements.txt
├── LICENSE
└── README.md
```

---

## How it works

### Optimisation model

**Type:** Constraint Programming (CP-SAT, Google OR-Tools)

**Objective — minimise total fleet cost:**

```
min  Σ c_i · x_ist  +  Σ r_i · y_it  +  Σ P · u_skt
```

| Symbol | Meaning |
|--------|---------|
| `x_ist` | Binary: equipment i assigned to site s on day t |
| `y_it` | Binary: equipment i relocated on day t |
| `u_skt` | Integer: unmet demand of type k at site s on day t |
| `c_i` | Daily rate for equipment i |
| `r_i` | Relocation cost for equipment i |
| `P` | Penalty per unmet demand-day |

**Constraints**

| | |
|---|---|
| (C1) | Each equipment at exactly one location per day |
| (C2) | Demand satisfaction with slack variables |
| (C3) | Relocation detection via site changes |
| (C4) | Maximum relocations per unit |
| (C5) | Equipment availability windows |

### Equipment types

| Type | Examples |
|------|----------|
| Excavator | CAT 320, Komatsu PC200, Volvo EC220 |
| Dump truck | KAMAZ 6520, Volvo FMX, Scania P440 |
| Concrete pump | Putzmeister 36Z, Schwing S39SX |
| Crane truck | Liebherr LTM 1060, Tadano GR-300 |
| Loader | CAT 950M, Volvo L120H, Komatsu WA320 |

### Site types

| Type | Demand profile |
|------|---------------|
| Residential | Medium excavators, high dump trucks, periodic concrete |
| Industrial | High excavators, very high dump trucks, regular cranes |
| Infrastructure | Very high excavators and dump trucks, regular cranes |

---

## Features

- **Demo dataset** — 3 sites, 20-day horizon, 22 units
- **Generator** — configurable sites, horizon, fleet size, rental fraction
- **KPI dashboard** — total cost, utilisation, relocations, unmet demand
- **Gantt chart** — equipment timeline across sites
- **Cost analysis** — breakdown pie + comparison bar charts
- **Greedy baseline** — compare CP-SAT optimal vs greedy assignment
- **Model tab** — full LaTeX formulation and run parameters

---

## License

MIT
