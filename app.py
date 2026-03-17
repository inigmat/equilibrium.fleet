"""
equilibrium.fleet — Equipment Fleet Optimiser
Streamlit application entry point.
"""

import streamlit as st
import pandas as pd
from solver import solve_fleet_greedy, solve_fleet_cpsat
from data_gen import generate_demo_scenario, generate_random_scenario
from charts import (
    TYPE_LABELS_RU,
    fig_gantt_fleet, fig_utilisation_bars, fig_cost_breakdown,
    fig_demand_heatmap, fig_comparison_bar, fig_relocations_timeline,
)
from input_loader import (
    EQUIPMENT_TYPES, EQUIPMENT_TYPE_LABELS_RU,
    DEFAULT_EQUIPMENT_DF, DEFAULT_DEMAND_DF,
    get_excel_template_bytes,
    parse_excel_to_problem,
    build_problem_from_manual,
)

st.set_page_config(
    page_title="equilibrium.fleet",
    page_icon="🚜",
    layout="wide",
)

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("🚜 equilibrium.fleet")
    st.caption("Construction Equipment Fleet Optimiser")
    st.divider()

    data_mode = st.radio(
        "Data source",
        ["Demo scenario", "Generator", "Excel", "Manual input"],
        index=0,
    )

    if data_mode == "Generator":
        n_sites = st.slider("Number of sites", 2, 6, 3)
        horizon = st.slider("Planning horizon (days)", 10, 40, 20)
        fleet_size = st.slider("Fleet size", 8, 30, 15)
        rental_frac = st.slider("Rental fraction", 0.0, 0.6, 0.3, 0.05)
        seed = st.number_input("Seed", 0, 999, 42)

    if data_mode == "Excel":
        st.divider()
        st.download_button(
            label="📥 Download Excel Template",
            data=get_excel_template_bytes(),
            file_name="fleet_template.xlsx",
            mime=(
                "application/vnd.openxmlformats-officedocument"
                ".spreadsheetml.sheet"
            ),
            width='stretch',
        )

    st.divider()
    st.subheader("Solver parameters")
    time_limit = st.slider("CP-SAT time limit (s)", 5, 120, 30)
    penalty = st.number_input(
        "Unmet demand penalty ($/day)", 100, 2000, 500, 100,
    )
    max_reloc = st.slider("Max relocations per unit", 1, 10, 4)

    st.divider()
    show_comparison = st.toggle("Compare with greedy baseline", value=True)
    show_advanced = st.toggle("Advanced analytics", value=False)

# ── Manual input editors ─────────────────────────────────────────────────────
if data_mode == "Manual input":
    st.markdown("## ✏️ Manual Data Entry")
    st.info(
        "Edit the tables below, then press **▶ Optimise** to run the solver."
    )

    col_eq, col_dem = st.columns([1, 1])

    with col_eq:
        st.markdown("### Fleet")
        eq_edited = st.data_editor(
            DEFAULT_EQUIPMENT_DF,
            key="manual_eq",
            num_rows="dynamic",
            width='stretch',
            column_config={
                "id": st.column_config.TextColumn(
                    "ID", width="small",
                ),
                "name": st.column_config.TextColumn("Name"),
                "type": st.column_config.SelectboxColumn(
                    "Type", options=EQUIPMENT_TYPES, required=True,
                ),
                "owned": st.column_config.CheckboxColumn(
                    "Owned", width="small",
                ),
                "daily_rate": st.column_config.NumberColumn(
                    "Daily rate $", min_value=0, step=10,
                ),
                "relocation_cost": st.column_config.NumberColumn(
                    "Relocation $", min_value=0, step=50,
                ),
                "capacity": st.column_config.NumberColumn(
                    "Capacity", min_value=1, step=10,
                ),
                "available_from": st.column_config.NumberColumn(
                    "From day", min_value=0, step=1, width="small",
                ),
                "available_to": st.column_config.NumberColumn(
                    "To day", min_value=0, step=1, width="small",
                ),
            },
        )

    with col_dem:
        st.markdown("### Site Demand")
        dem_edited = st.data_editor(
            DEFAULT_DEMAND_DF,
            key="manual_dem",
            num_rows="dynamic",
            width='stretch',
            column_config={
                "site_id": st.column_config.TextColumn(
                    "Site ID", width="small",
                ),
                "site_name": st.column_config.TextColumn("Site name"),
                "equipment_type": st.column_config.SelectboxColumn(
                    "Type", options=EQUIPMENT_TYPES, required=True,
                ),
                "day": st.column_config.NumberColumn(
                    "Day", min_value=0, step=1, width="small",
                ),
                "quantity_needed": st.column_config.NumberColumn(
                    "Qty", min_value=1, step=1, width="small",
                ),
                "min_capacity": st.column_config.NumberColumn(
                    "Min capacity", min_value=0, step=10, width="small",
                ),
            },
        )

    st.markdown(
        "> **Equipment types:** `excavator` · `dump_truck` · "
        "`concrete_pump` · `crane_truck` · `loader`"
    )
    st.divider()

# ── Excel upload ─────────────────────────────────────────────────────────────
if data_mode == "Excel":
    st.markdown("## 📂 Upload Excel Data")
    uploaded_file = st.file_uploader(
        "Upload your filled Excel file "
        "(use the template from the sidebar)",
        type=["xlsx", "xls"],
        key="excel_upload",
    )
    if uploaded_file is None:
        st.info(
            "Download the template via **📥 Download Excel Template** "
            "in the sidebar, fill in the **Equipment** and **Demand** "
            "sheets, then upload the file here."
        )
    st.divider()

# ── Generate problem ─────────────────────────────────────────────────────────
_parse_error: str | None = None
_parse_warnings: list[str] = []

if data_mode == "Demo scenario":
    problem = generate_demo_scenario()
elif data_mode == "Generator":
    problem = generate_random_scenario(
        n_sites, horizon, fleet_size, rental_frac, seed,
    )
elif data_mode == "Excel":
    if uploaded_file is not None:
        try:
            problem, _parse_warnings = parse_excel_to_problem(
                uploaded_file, penalty, max_reloc,
            )
        except ValueError as e:
            _parse_error = str(e)
            problem = generate_demo_scenario()
    else:
        problem = generate_demo_scenario()
else:  # Manual input
    try:
        problem, _parse_warnings = build_problem_from_manual(
            eq_edited, dem_edited, penalty, max_reloc,
        )
    except (ValueError, NameError) as e:
        _parse_error = str(e)
        problem = generate_demo_scenario()

problem.penalty_unmet = penalty
problem.max_relocations_per_unit = max_reloc

if _parse_error:
    st.error(f"❌ Data load error: {_parse_error}")
if _parse_warnings:
    with st.expander(f"⚠️ Load warnings ({len(_parse_warnings)})"):
        for w in _parse_warnings:
            st.warning(w)

# ── Header + run button ──────────────────────────────────────────────────────
st.markdown("# 🚜 Construction Equipment Fleet Optimiser")

if "solution" not in st.session_state:
    st.markdown("""
**equilibrium.fleet** solves the optimal allocation of construction equipment
across multiple sites over a planning horizon.

The system minimises total costs — daily rental / ownership rates, relocation
costs, and penalties for unmet demand — while respecting each unit's
availability window.

**When it works best:**
- Fleet of 5+ units spread across 2 or more active sites
- Equipment regularly sits idle at one site while another site is short
- High relocation costs make it worth planning moves carefully
- Planning horizon of 1–2 weeks or more, where manual analysis is tedious
- Part of the fleet is rented with fixed availability windows that must
  be utilised efficiently
""")
    st.info(
        "Select a data source in the sidebar, "
        "then press **▶ Optimise** below."
    )

_, btn_col, _ = st.columns([2, 1, 2])
with btn_col:
    run_btn = st.button("▶ Optimise", type="primary", width='stretch')

# ── Solve ────────────────────────────────────────────────────────────────────
if run_btn:
    with st.spinner("Running CP-SAT solver..."):
        solution = solve_fleet_cpsat(problem, time_limit=time_limit)
        st.session_state["solution"] = solution

    if show_comparison:
        with st.spinner("Running greedy baseline..."):
            greedy = solve_fleet_greedy(problem)
            st.session_state["greedy"] = greedy
    else:
        st.session_state["greedy"] = None

if "solution" not in st.session_state:
    st.stop()

solution = st.session_state["solution"]
greedy = st.session_state.get("greedy")

st.markdown(
    f"**Sites:** {len(problem.sites)} · "
    f"**Horizon:** {problem.horizon} days · "
    f"**Fleet:** {len(problem.equipment)} units · "
    f"**Status:** {solution.status} · "
    f"**Solve time:** {solution.solve_time:.2f}s"
)

# ── KPI Cards ────────────────────────────────────────────────────────────────
if solution.summary:
    cols = st.columns(5)
    s = solution.summary
    cb = solution.cost_breakdown
    operational_cost = cb["rental"] + cb["relocation"]

    with cols[0]:
        st.metric("💰 Operational cost", f"${operational_cost:,.0f}")
    with cols[1]:
        st.metric("🔧 Units assigned", f"{s['units_assigned']}")
    with cols[2]:
        st.metric("🚛 Relocations", f"{s['total_relocations']}")
    with cols[3]:
        st.metric("⚠️ Unmet demand-days", f"{s['unmet_demand_days']}")
    with cols[4]:
        st.metric("📊 Avg utilisation", f"{s['avg_utilisation']}%")

    if cb["penalty"] > 0:
        st.warning(
            f"Demand gap: \\${cb['penalty']:,.0f} in model penalties — "
            f"{s['unmet_demand_days']} demand-days unmet "
            f"× \\${penalty}/day. "
            "This is not a real expenditure — it reflects a supply "
            "shortfall. Consider adding units of the scarce type."
        )

    if greedy and greedy.summary and show_comparison:
        g_total = greedy.summary["total_cost"]
        cp_total = s["total_cost"]
        savings = g_total - cp_total
        pct = 100 * savings / max(g_total, 1)
        if savings > 0:
            st.success(
                f"✅ Total cost savings vs greedy baseline: "
                f"**\\${savings:,.0f}** ({pct:.1f}%)"
            )
        elif savings < 0:
            st.info(
                f"Greedy shows lower total cost by \\${-savings:,.0f}. "
                "CP-SAT charges rental for every day equipment stays "
                "at a site (including idle days); greedy only charges "
                "on days with active demand — so costs are not "
                "directly comparable on sparse schedules."
            )

# ── Main Tabs ────────────────────────────────────────────────────────────────
if show_advanced:
    tab_names = [
        "📅 Schedule", "📊 Utilisation", "💰 Costs",
        "🚛 Relocations", "🔥 Demand", "📐 Model", "📖 Guide",
    ]
else:
    tab_names = ["📅 Schedule", "📊 Utilisation", "💰 Costs", "📖 Guide"]

tabs = st.tabs(tab_names)

# ── Tab: Schedule ────────────────────────────────────────────────────────────
with tabs[0]:
    st.plotly_chart(
        fig_gantt_fleet(solution.assignments, problem.horizon),
        width='stretch',
    )
    if not solution.assignments.empty:
        with st.expander("Assignment table"):
            display_df = solution.assignments.copy()
            display_df["type_label"] = (
                display_df["equipment_type"].map(TYPE_LABELS_RU)
            )
            st.dataframe(
                display_df[[
                    "equipment_name", "type_label", "site_name",
                    "day", "daily_cost", "relocation_cost",
                ]].rename(columns={
                    "equipment_name":  "Equipment",
                    "type_label":      "Type",
                    "site_name":       "Site",
                    "day":             "Day",
                    "daily_cost":      "Daily rate, $",
                    "relocation_cost": "Relocation, $",
                }),
                hide_index=True,
                width='stretch',
            )

# ── Tab: Utilisation ─────────────────────────────────────────────────────────
with tabs[1]:
    st.plotly_chart(
        fig_utilisation_bars(solution.utilisation), width='stretch',
    )
    if show_comparison and greedy:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**CP-SAT (optimal)**")
            st.metric(
                "Avg utilisation",
                f"{solution.summary.get('avg_utilisation', 0)}%",
            )
        with col2:
            st.markdown("**Greedy baseline**")
            st.metric(
                "Avg utilisation",
                f"{greedy.summary.get('avg_utilisation', 0)}%",
            )

# ── Tab: Costs ───────────────────────────────────────────────────────────────
with tabs[2]:
    if show_comparison and greedy:
        st.plotly_chart(
            fig_comparison_bar(greedy.summary, solution.summary),
            width='stretch',
        )
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(
                fig_cost_breakdown(greedy.cost_breakdown, "(Greedy)"),
                width='stretch',
            )
        with c2:
            st.plotly_chart(
                fig_cost_breakdown(solution.cost_breakdown, "(CP-SAT)"),
                width='stretch',
            )
    else:
        st.plotly_chart(
            fig_cost_breakdown(solution.cost_breakdown), width='stretch',
        )

# ── Advanced tabs ────────────────────────────────────────────────────────────
if show_advanced:
    with tabs[3]:
        st.plotly_chart(
            fig_relocations_timeline(solution.relocations, problem.horizon),
            width='stretch',
        )
        if not solution.relocations.empty:
            st.dataframe(
                solution.relocations.rename(columns={
                    "equipment_name": "Equipment",
                    "from_site":      "From",
                    "to_site":        "To",
                    "day":            "Day",
                    "cost":           "Cost, $",
                }),
                hide_index=True,
                width='stretch',
            )

    with tabs[4]:
        demands_df = pd.DataFrame([{
            "site_id":        d.site_id,
            "site_name":      d.site_name,
            "equipment_type": d.equipment_type,
            "day":            d.day,
            "quantity_needed": d.quantity_needed,
        } for d in problem.demands])
        st.plotly_chart(
            fig_demand_heatmap(demands_df, problem.horizon),
            width='stretch',
        )
        if not solution.unmet_demands.empty:
            st.warning(
                f"⚠️ Unmet demand: {len(solution.unmet_demands)} records"
            )
            st.dataframe(
                solution.unmet_demands.rename(columns={
                    "site_name":      "Site",
                    "equipment_type": "Type",
                    "day":            "Day",
                    "shortfall":      "Shortfall",
                    "penalty":        "Penalty, $",
                }),
                hide_index=True,
            )
        else:
            st.success("✅ All demand satisfied")

    with tabs[5]:
        st.markdown("### Mathematical formulation")
        st.latex(
            r"\min \sum_{i,s,t} c_i \cdot x_{ist}"
            r"+ \sum_{i,t} r_i \cdot y_{it}"
            r"+ \sum_{s,k,t} P \cdot u_{skt}"
        )
        st.markdown("**Where:**")
        st.markdown(r"""
- $x_{ist} \in \{0,1\}$ — unit $i$ assigned to site $s$ on day $t$
- $y_{it} \in \{0,1\}$ — unit $i$ relocated on day $t$
- $u_{skt} \geq 0$ — unmet demand of type $k$ at site $s$ on day $t$
- $c_i$ — daily rate, $r_i$ — relocation cost, $P$ — penalty
        """)
        st.markdown("**Constraints:**")
        st.latex(
            r"\sum_s x_{ist} = 1 \quad \forall i, t"
            r"\quad \text{(each unit at exactly one site)}"
        )
        st.latex(
            r"\sum_{i \in T_k} x_{ist} + u_{skt} \geq d_{skt}"
            r"\quad \text{(demand satisfaction)}"
        )
        st.latex(
            r"y_{it} \geq x_{is,t-1} - x_{ist}"
            r"\quad \text{(relocation tracking)}"
        )
        st.latex(
            r"\sum_t y_{it} \leq M_{\max}"
            r"\quad \text{(relocation limit per unit)}"
        )
        st.divider()
        st.markdown("**Current run parameters:**")
        st.json({
            "equipment_count":  len(problem.equipment),
            "sites":            len(problem.sites),
            "horizon_days":     problem.horizon,
            "penalty_unmet":    problem.penalty_unmet,
            "max_relocations":  problem.max_relocations_per_unit,
            "solver_time_limit": time_limit,
            "status":           solution.status,
            "objective":        round(solution.objective, 2),
            "solve_time_s":     round(solution.solve_time, 3),
        })

# ── Tab: Guide ───────────────────────────────────────────────────────────────
guide_tab = tabs[-1]
with guide_tab:
    st.markdown("## 📖 User Guide")
    st.markdown("""
**equilibrium.fleet** optimally distributes construction equipment across
sites over a planning horizon, minimising total cost: rental/ownership
rates, relocation costs, and unmet-demand penalties.
""")

    st.markdown("### 🚀 Quick start")
    st.markdown("""
1. Choose a data source in the sidebar
2. Adjust solver parameters if needed
3. Press **▶ Optimise**
4. Explore results in the **Schedule**, **Utilisation**, and **Costs** tabs
""")

    st.divider()
    st.markdown("### 📊 Data sources")

    with st.expander("🔵 Demo scenario", expanded=False):
        st.markdown("""
A ready-made example: **3 sites · 22 units · 20-day horizon**.

- Riverside Apartments (residential)
- Industrial Plant A (industrial)
- Highway M-12 Sec.3 (infrastructure)

Use this to explore the interface before loading your own data.
""")

    with st.expander("🟢 Random generator", expanded=False):
        st.markdown("""
Generates a random scenario. Parameters:

| Parameter | Range | Description |
|-----------|-------|-------------|
| Number of sites | 2–6 | Construction sites |
| Planning horizon | 10–40 days | Optimisation window |
| Fleet size | 8–30 units | Total number of machines |
| Rental fraction | 0–60% | Share of fleet that is rented |
| Seed | 0–999 | Fix for reproducibility |

The same seed always produces the same scenario.
""")

    with st.expander("🟡 Excel upload", expanded=True):
        st.markdown("""
**Step 1.** Download the template via **📥 Download Excel Template**
in the sidebar.

**Step 2.** Fill in two sheets:

---
**Sheet "Equipment"** — list of machines:

| Column | Type | Description |
|--------|------|-------------|
| `id` | text | Unique ID (e.g. `EQ-001`) |
| `name` | text | Display name |
| `type` | text | Type key (see table below) |
| `owned` | TRUE/FALSE | Company-owned or rental |
| `daily_rate` | number ($) | Daily rate |
| `relocation_cost` | number ($) | Cost per relocation |
| `capacity` | number | Productivity (units/day) |
| `available_from` | integer | First available day (0 = day 1) |
| `available_to` | integer | Last available day (inclusive) |

---
**Sheet "Demand"** — site demand by day:

| Column | Type | Description |
|--------|------|-------------|
| `site_id` | text | Site ID (`S1`, `S2`, ...) |
| `site_name` | text | Site display name |
| `equipment_type` | text | Type key (see table below) |
| `day` | integer | Day index (0 = first day) |
| `quantity_needed` | integer | Units required |
| `min_capacity` | number | Min productivity threshold (0 = none) |

---
**Step 3.** Upload the filled file in the upload area above.

**Step 4.** Press **▶ Optimise**.
""")
        st.markdown("**Valid equipment type keys:**")
        types_df = pd.DataFrame({
            "`type` value": list(EQUIPMENT_TYPE_LABELS_RU.keys()),
            "Label":        list(EQUIPMENT_TYPE_LABELS_RU.values()),
        })
        st.dataframe(types_df, hide_index=True, width='stretch')

    with st.expander("🟠 Manual input", expanded=False):
        st.markdown("""
Fill in the fleet and demand tables directly in the browser — no Excel needed.

- **Add a row:** click **+** at the bottom of the table
- **Delete a row:** select the row → press Delete
- **Equipment type** is chosen from a dropdown

After filling the tables, press **▶ Optimise** in the sidebar.

> Data exists only for the current browser session.
> For permanent storage use the Excel workflow.
""")

    st.divider()
    st.markdown("### ⚙️ Solver parameters")
    st.markdown("""
| Parameter | Default | Description |
|-----------|---------|-------------|
| CP-SAT time limit | 30 s | Increase for large problems (>20 units, >30 days)|
| Unmet demand penalty | $500/day | Higher → aggressively closes demand gaps |
| Max relocations per unit | 4 | Cap on how many times one machine can move |
""")

    st.divider()
    st.markdown("### 📈 Reading the results")
    st.markdown("""
**KPI cards:**
- **Operational cost** — real expenditure: rental rates + relocation costs
- **Units assigned** — machines that received at least one assignment
- **Relocations** — total number of site-to-site moves
- **Unmet demand-days** — days where demand was not fully covered
  (0 = all demand satisfied)
- **Avg utilisation** — average % of available days a machine is assigned

> If any demand goes unmet, a **demand gap warning** appears below the
> cards showing the model penalty amount. This is *not* a real cost —
> it is a solver signal that the fleet lacks units of a certain type.
> Penalty size = unmet demand-days × penalty rate ($/day).

**Result tabs:**
- **📅 Schedule** — Gantt chart showing where each machine works each day
- **📊 Utilisation** — utilisation % per machine
- **💰 Costs** — cost breakdown (rental / relocations / penalties)

**Greedy comparison:**
Shows savings of CP-SAT over a simple heuristic.
The larger the problem, the higher the potential saving.
""")

    st.divider()
    st.markdown("### 💡 Tips")
    st.markdown("""
- The **horizon** is derived automatically from the maximum day in demand data
- `available_to` is clipped to the horizon — no need to match exactly
- If status is **FEASIBLE** (not OPTIMAL) — increase the solver time limit
- High penalty (> 100 000 $) forces the solver to close all demand at any cost;
  low penalty allows some shortfall
- Enable **Advanced analytics** for detailed relocation and demand-by-day views
""")

# ── Footer ───────────────────────────────────────────────────────────────────
st.divider()
st.caption(
    "equilibrium.fleet · Construction Equipment Fleet Optimiser · "
    "CP-SAT (OR-Tools) + Streamlit"
)
