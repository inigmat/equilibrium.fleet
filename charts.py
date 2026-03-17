"""
equilibrium.fleet — Plotly Visualisations
"""

import plotly.graph_objects as go
import plotly.express as px
import pandas as pd

# Consistent color palette
SITE_COLORS = px.colors.qualitative.Set2
TYPE_COLORS = {
    "excavator":     "#E74C3C",
    "dump_truck":    "#3498DB",
    "concrete_pump": "#2ECC71",
    "crane_truck":   "#F39C12",
    "loader":        "#9B59B6",
}
TYPE_LABELS_RU = {
    "excavator":     "Excavator",
    "dump_truck":    "Dump Truck",
    "concrete_pump": "Concrete Pump",
    "crane_truck":   "Crane Truck",
    "loader":        "Loader",
}


def fig_gantt_fleet(assignments: pd.DataFrame, horizon: int) -> go.Figure:
    """Gantt chart: equipment assignment timeline across sites."""
    if assignments.empty:
        return go.Figure().update_layout(title="No data")

    # Group consecutive days at same site into bars
    df = assignments.sort_values(["equipment_id", "day"]).copy()
    bars = []
    for eq_id, grp in df.groupby("equipment_id"):
        grp = grp.sort_values("day")
        eq_name = grp.iloc[0]["equipment_name"]
        eq_type = grp.iloc[0]["equipment_type"]

        segments = []
        cur_site = None
        start_day = None
        site_name = None
        prev_day = None

        for _, row in grp.iterrows():
            if row["site_id"] != cur_site:
                if cur_site is not None:
                    segments.append(
                        (start_day, prev_day, cur_site, site_name)
                    )
                cur_site = row["site_id"]
                site_name = row["site_name"]
                start_day = row["day"]
            prev_day = row["day"]
        if cur_site is not None:
            segments.append((start_day, prev_day, cur_site, site_name))

        for s_day, e_day, site_id, s_name in segments:
            bars.append({
                "equipment": eq_name,
                "eq_type":   eq_type,
                "site_id":   site_id,
                "site_name": s_name,
                "start":     s_day,
                "end":       e_day + 1,
                "duration":  e_day - s_day + 1,
            })

    bar_df = pd.DataFrame(bars)

    # Assign colors by site
    unique_sites = bar_df["site_id"].unique()
    site_color_map = {
        s: SITE_COLORS[i % len(SITE_COLORS)]
        for i, s in enumerate(unique_sites)
    }

    fig = go.Figure()
    for site_id in unique_sites:
        site_bars = bar_df[bar_df["site_id"] == site_id]
        site_name = site_bars.iloc[0]["site_name"]
        fig.add_trace(go.Bar(
            y=site_bars["equipment"],
            x=site_bars["duration"],
            base=site_bars["start"],
            orientation="h",
            name=site_name,
            marker_color=site_color_map[site_id],
            hovertemplate=(
                "<b>%{y}</b><br>"
                f"Site: {site_name}<br>"
                "Days: %{base} – %{x}<br>"
                "<extra></extra>"
            ),
        ))

    fig.update_layout(
        barmode="stack",
        title="📅 Equipment Assignment Schedule",
        xaxis_title="Planning Day",
        yaxis_title="",
        xaxis=dict(range=[0, horizon], dtick=1),
        height=max(400, len(bar_df["equipment"].unique()) * 32 + 100),
        legend_title="Sites",
        yaxis=dict(autorange="reversed"),
        margin=dict(l=200),
    )
    return fig


def fig_utilisation_bars(utilisation: pd.DataFrame) -> go.Figure:
    """Horizontal bar chart of equipment utilisation percentage."""
    if utilisation.empty:
        return go.Figure().update_layout(title="No data")

    df = utilisation.sort_values("utilisation_pct", ascending=True).copy()
    df["type_label"] = df["equipment_type"].map(TYPE_LABELS_RU)
    df["color"] = df["equipment_type"].map(TYPE_COLORS)

    fig = go.Figure()
    fig.add_trace(go.Bar(
        y=df["equipment_name"],
        x=df["utilisation_pct"],
        orientation="h",
        marker_color=df["color"],
        text=df["utilisation_pct"].apply(lambda v: f"{v:.0f}%"),
        textposition="auto",
        hovertemplate=(
            "<b>%{y}</b><br>"
            "Utilisation: %{x:.1f}%<br>"
            "<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="📊 Equipment Utilisation",
        xaxis_title="Utilisation, %",
        xaxis=dict(range=[0, 105]),
        height=max(350, len(df) * 28 + 100),
        margin=dict(l=200),
        showlegend=False,
    )
    return fig


def fig_cost_breakdown(
    cost_breakdown: dict, title_suffix: str = ""
) -> go.Figure:
    """Pie chart of cost components."""
    labels = ["Rental / depreciation", "Relocation", "Unmet demand penalties"]
    values = [
        cost_breakdown["rental"],
        cost_breakdown["relocation"],
        cost_breakdown["penalty"],
    ]
    colors = ["#3498DB", "#F39C12", "#E74C3C"]

    filtered = [
        (lbl, v, c) for lbl, v, c in zip(labels, values, colors) if v > 0
    ]
    if not filtered:
        return go.Figure().update_layout(title="No costs")

    labels_f, values_f, colors_f = zip(*filtered)  # type: ignore[misc]

    fig = go.Figure(data=[go.Pie(
        labels=labels_f,
        values=values_f,
        marker_colors=colors_f,
        hole=0.45,
        textinfo="label+percent",
        hovertemplate="<b>%{label}</b><br>$%{value:,.0f}<extra></extra>",
    )])

    fig.update_layout(
        title=f"💰 Cost Breakdown {title_suffix}",
        height=350,
    )
    return fig


def fig_demand_heatmap(
    demands_df: pd.DataFrame, horizon: int
) -> go.Figure:
    """Heatmap: demand by equipment type and day."""
    if demands_df.empty:
        return go.Figure().update_layout(title="No data")

    pivot = (
        demands_df
        .groupby(["equipment_type", "day"])["quantity_needed"]
        .sum()
        .reset_index()
    )
    pivot["type_label"] = pivot["equipment_type"].map(TYPE_LABELS_RU)

    matrix = pivot.pivot_table(
        index="type_label", columns="day",
        values="quantity_needed", fill_value=0,
    )

    fig = go.Figure(data=go.Heatmap(
        z=matrix.values,
        x=[f"D{d}" for d in matrix.columns],
        y=matrix.index,
        colorscale="YlOrRd",
        hovertemplate=(
            "Type: %{y}<br>Day: %{x}<br>Demand: %{z}<extra></extra>"
        ),
    ))

    fig.update_layout(
        title="🔥 Equipment Demand Heatmap",
        xaxis_title="Day",
        yaxis_title="",
        height=300,
    )
    return fig


def fig_comparison_bar(
    summary_greedy: dict, summary_optimal: dict
) -> go.Figure:
    """Side-by-side comparison of greedy vs optimal costs."""
    categories = ["Rental", "Relocation", "Penalties", "TOTAL"]
    greedy_vals = [
        summary_greedy.get("rental_cost", 0),
        summary_greedy.get("relocation_cost", 0),
        summary_greedy.get("penalty_cost", 0),
        summary_greedy.get("total_cost", 0),
    ]
    optimal_vals = [
        summary_optimal.get("rental_cost", 0),
        summary_optimal.get("relocation_cost", 0),
        summary_optimal.get("penalty_cost", 0),
        summary_optimal.get("total_cost", 0),
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        name="Greedy (baseline)",
        x=categories, y=greedy_vals,
        marker_color="#E74C3C",
        text=[f"{v:,.0f}" for v in greedy_vals],
        textposition="auto",
    ))
    fig.add_trace(go.Bar(
        name="CP-SAT (optimal)",
        x=categories, y=optimal_vals,
        marker_color="#2ECC71",
        text=[f"{v:,.0f}" for v in optimal_vals],
        textposition="auto",
    ))

    fig.update_layout(
        barmode="group",
        title="⚡ Comparison: Greedy vs CP-SAT",
        yaxis_title="Cost, $",
        height=400,
    )
    return fig


def fig_relocations_timeline(
    relocations: pd.DataFrame, horizon: int
) -> go.Figure:
    """Timeline of equipment relocations."""
    if relocations.empty:
        return go.Figure().update_layout(title="No relocations")

    fig = go.Figure()
    for _, row in relocations.iterrows():
        fig.add_trace(go.Scatter(
            x=[row["day"]],
            y=[row["equipment_name"]],
            mode="markers+text",
            marker=dict(size=14, symbol="arrow-right", color="#F39C12"),
            text=[f"→ {row['to_site']}"],
            textposition="middle right",
            hovertemplate=(
                f"<b>{row['equipment_name']}</b><br>"
                f"From: {row['from_site']} → To: {row['to_site']}<br>"
                f"Day: {row['day']}<br>"
                f"Cost: ${row['cost']:,.0f}<br>"
                "<extra></extra>"
            ),
            showlegend=False,
        ))

    fig.update_layout(
        title="🚛 Equipment Relocations",
        xaxis_title="Day",
        xaxis=dict(range=[0, horizon], dtick=1),
        height=max(
            300,
            len(relocations["equipment_name"].unique()) * 30 + 100,
        ),
        margin=dict(l=200),
    )
    return fig
