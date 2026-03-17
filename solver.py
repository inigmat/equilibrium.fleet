"""
equilibrium.fleet — Equipment Fleet Optimiser
Solver module: MILP model for optimal assignment of construction equipment
across multiple sites over a planning horizon.

Objective: minimise total cost = rental + relocation + idle penalties
Subject to: demand satisfaction, capacity, availability windows
"""

from dataclasses import dataclass
from ortools.sat.python import cp_model
import pandas as pd


@dataclass
class Equipment:
    id: str
    name: str
    type: str  # excavator, dump_truck, concrete_pump, crane_truck, loader
    owned: bool
    daily_rate: float       # cost per day (rental or internal rate)
    relocation_cost: float  # cost to move between sites
    capacity: float         # productivity units per day
    available_from: int     # day index
    available_to: int       # day index


@dataclass
class SiteDemand:
    site_id: str
    site_name: str
    equipment_type: str
    day: int
    quantity_needed: int  # number of units needed
    min_capacity: float   # minimum productivity required


@dataclass
class FleetProblem:
    equipment: list[Equipment]
    demands: list[SiteDemand]
    horizon: int             # planning horizon in days
    sites: list[str]
    site_names: dict[str, str]
    penalty_unmet: float = 500.0  # penalty per unmet demand-day
    max_relocations_per_unit: int = 5


@dataclass
class FleetSolution:
    status: str
    objective: float
    assignments: pd.DataFrame   # equipment_id, site_id, day, cost
    summary: dict
    relocations: pd.DataFrame
    unmet_demands: pd.DataFrame
    utilisation: pd.DataFrame   # per-equipment utilisation %
    cost_breakdown: dict
    solve_time: float


def solve_fleet_greedy(problem: FleetProblem) -> FleetSolution:
    """Greedy baseline: cheapest available unit to highest-demand site."""
    import time
    t0 = time.time()

    assignments: list[dict] = []
    relocations: list[dict] = []
    unmet: list[dict] = []

    equipment_location = {eq.id: None for eq in problem.equipment}
    equipment_assigned = {eq.id: set() for eq in problem.equipment}

    demands_by_day: dict[int, list] = {}
    for d in problem.demands:
        demands_by_day.setdefault(d.day, []).append(d)

    total_rental = 0.0
    total_relocation = 0.0
    total_penalty = 0.0

    for day in range(problem.horizon):
        day_demands = demands_by_day.get(day, [])
        day_demands.sort(key=lambda x: x.quantity_needed, reverse=True)

        for demand in day_demands:
            candidates = [
                eq for eq in problem.equipment
                if eq.type == demand.equipment_type
                and day not in equipment_assigned[eq.id]
                and eq.available_from <= day <= eq.available_to
            ]
            candidates.sort(
                key=lambda eq: (0 if eq.owned else 1, eq.daily_rate)
            )

            assigned_count = 0
            for eq in candidates:
                if assigned_count >= demand.quantity_needed:
                    break

                reloc_cost = 0.0
                cur_loc = equipment_location[eq.id]
                if cur_loc is not None and cur_loc != demand.site_id:
                    reloc_cost = eq.relocation_cost
                    relocations.append({
                        "equipment_id":   eq.id,
                        "equipment_name": eq.name,
                        "from_site":      cur_loc,
                        "to_site":        demand.site_id,
                        "day":            day,
                        "cost":           reloc_cost,
                    })

                site_name = problem.site_names.get(
                    demand.site_id, demand.site_id
                )
                assignments.append({
                    "equipment_id":   eq.id,
                    "equipment_name": eq.name,
                    "equipment_type": eq.type,
                    "site_id":        demand.site_id,
                    "site_name":      site_name,
                    "day":            day,
                    "daily_cost":     eq.daily_rate,
                    "relocation_cost": reloc_cost,
                    "owned":          eq.owned,
                })

                total_rental += eq.daily_rate
                total_relocation += reloc_cost
                equipment_location[eq.id] = demand.site_id
                equipment_assigned[eq.id].add(day)
                assigned_count += 1

            shortfall = demand.quantity_needed - assigned_count
            if shortfall > 0:
                total_penalty += shortfall * problem.penalty_unmet
                site_name = problem.site_names.get(
                    demand.site_id, demand.site_id
                )
                unmet.append({
                    "site_id":        demand.site_id,
                    "site_name":      site_name,
                    "equipment_type": demand.equipment_type,
                    "day":            day,
                    "shortfall":      shortfall,
                    "penalty":        shortfall * problem.penalty_unmet,
                })

    _ASSIGN_COLS = [
        "equipment_id", "equipment_name", "equipment_type",
        "site_id", "site_name", "day",
        "daily_cost", "relocation_cost", "owned",
    ]
    _RELOC_COLS = [
        "equipment_id", "equipment_name",
        "from_site", "to_site", "day", "cost",
    ]
    _UNMET_COLS = [
        "site_id", "site_name", "equipment_type",
        "day", "shortfall", "penalty",
    ]

    df_assign = (
        pd.DataFrame(assignments) if assignments
        else pd.DataFrame(columns=_ASSIGN_COLS)
    )
    df_reloc = (
        pd.DataFrame(relocations) if relocations
        else pd.DataFrame(columns=_RELOC_COLS)
    )
    df_unmet = (
        pd.DataFrame(unmet) if unmet
        else pd.DataFrame(columns=_UNMET_COLS)
    )

    util_rows = []
    for eq in problem.equipment:
        avail_days = eq.available_to - eq.available_from + 1
        used_days = len(equipment_assigned[eq.id])
        util_rows.append({
            "equipment_id":   eq.id,
            "equipment_name": eq.name,
            "equipment_type": eq.type,
            "owned":          eq.owned,
            "available_days": avail_days,
            "used_days":      used_days,
            "utilisation_pct": round(
                100 * used_days / max(avail_days, 1), 1
            ),
            "total_cost": eq.daily_rate * used_days,
        })
    df_util = pd.DataFrame(util_rows)

    objective = total_rental + total_relocation + total_penalty

    return FleetSolution(
        status="FEASIBLE",
        objective=objective,
        assignments=df_assign,
        summary={
            "total_cost":       objective,
            "rental_cost":      total_rental,
            "relocation_cost":  total_relocation,
            "penalty_cost":     total_penalty,
            "units_assigned": (
                len(set(df_assign["equipment_id"]))
                if len(df_assign) > 0 else 0
            ),
            "total_relocations": len(relocations),
            "unmet_demand_days": (
                int(df_unmet["shortfall"].sum())
                if len(df_unmet) > 0 else 0
            ),
            "avg_utilisation": (
                round(df_util["utilisation_pct"].mean(), 1)
                if len(df_util) > 0 else 0
            ),
        },
        relocations=df_reloc,
        unmet_demands=df_unmet,
        utilisation=df_util,
        cost_breakdown={
            "rental":     total_rental,
            "relocation": total_relocation,
            "penalty":    total_penalty,
        },
        solve_time=time.time() - t0,
    )


def solve_fleet_cpsat(
    problem: FleetProblem, time_limit: int = 30
) -> FleetSolution:
    """CP-SAT optimal solver for fleet assignment."""
    import time
    t0 = time.time()

    model = cp_model.CpModel()
    E = problem.equipment
    H = problem.horizon
    sites = problem.sites

    # Index demands by (site, type, day)
    demand_map: dict[tuple, int] = {}
    for d in problem.demands:
        key = (d.site_id, d.equipment_type, d.day)
        demand_map[key] = demand_map.get(key, 0) + d.quantity_needed

    # Decision variables: x[i,s,t] = 1 if unit i is at site s on day t
    # "_depot" represents idle / unavailable
    all_sites = sites + ["_depot"]

    x: dict = {}
    for i, eq in enumerate(E):
        for s in all_sites:
            for t in range(H):
                if eq.available_from <= t <= eq.available_to:
                    x[i, s, t] = model.NewBoolVar(f"x_{i}_{s}_{t}")
                else:
                    x[i, s, t] = model.NewConstant(
                        1 if s == "_depot" else 0
                    )

    # Each unit at exactly one site per day
    for i, eq in enumerate(E):
        for t in range(H):
            if eq.available_from <= t <= eq.available_to:
                model.Add(sum(x[i, s, t] for s in all_sites) == 1)

    # Relocation tracking: r[i,t] = 1 if unit i moves between t-1 and t
    r: dict = {}
    for i, eq in enumerate(E):
        for t in range(1, H):
            r[i, t] = model.NewBoolVar(f"r_{i}_{t}")
            for s in all_sites:
                # linearisation: r >= x[s,t-1] - x[s,t]
                model.Add(r[i, t] >= x[i, s, t - 1] - x[i, s, t])

    # Unmet demand slack variables
    unmet: dict = {}
    for key, qty in demand_map.items():
        site_id, eq_type, day = key
        unmet[key] = model.NewIntVar(
            0, qty, f"unmet_{site_id}_{eq_type}_{day}"
        )

    # Demand satisfaction
    type_equipment: dict[str, list] = {}
    for i, eq in enumerate(E):
        type_equipment.setdefault(eq.type, []).append(i)

    for (site_id, eq_type, day), qty in demand_map.items():
        eq_indices = type_equipment.get(eq_type, [])
        supply = sum(
            x[i, site_id, day]
            for i in eq_indices
            if (i, site_id, day) in x
        )
        model.Add(supply + unmet[(site_id, eq_type, day)] >= qty)

    # Relocation limit per unit
    for i, eq in enumerate(E):
        reloc_vars = [r[i, t] for t in range(1, H) if (i, t) in r]
        if reloc_vars:
            model.Add(
                sum(reloc_vars) <= problem.max_relocations_per_unit
            )

    # Objective — scale floats to integers for CP-SAT
    SCALE = 100

    rental_terms = [
        int(eq.daily_rate * SCALE) * x[i, s, t]
        for i, eq in enumerate(E)
        for s in sites
        for t in range(H)
        if (i, s, t) in x
    ]
    reloc_terms = [
        int(eq.relocation_cost * SCALE) * r[i, t]
        for i, eq in enumerate(E)
        for t in range(1, H)
        if (i, t) in r
    ]
    penalty_terms = [
        int(problem.penalty_unmet * SCALE) * unmet[key]
        for key in unmet
    ]

    model.Minimize(
        sum(rental_terms) + sum(reloc_terms) + sum(penalty_terms)
    )

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_workers = 4
    status = solver.Solve(model)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return FleetSolution(
            status="INFEASIBLE",
            objective=float("inf"),
            assignments=pd.DataFrame(),
            summary={},
            relocations=pd.DataFrame(),
            unmet_demands=pd.DataFrame(),
            utilisation=pd.DataFrame(),
            cost_breakdown={},
            solve_time=time.time() - t0,
        )

    # Extract solution
    assignments: list[dict] = []
    relocation_list: list[dict] = []
    equipment_used_days = {eq.id: 0 for eq in E}
    total_rental = 0.0
    total_relocation = 0.0

    for i, eq in enumerate(E):
        prev_site = None
        for t in range(H):
            for s in sites:
                if (i, s, t) in x and solver.Value(x[i, s, t]) == 1:
                    reloc_cost = 0.0
                    if (prev_site is not None
                            and prev_site != s
                            and prev_site != "_depot"):
                        reloc_cost = eq.relocation_cost
                        relocation_list.append({
                            "equipment_id":   eq.id,
                            "equipment_name": eq.name,
                            "from_site":      prev_site,
                            "to_site":        s,
                            "day":            t,
                            "cost":           reloc_cost,
                        })
                        total_relocation += reloc_cost

                    assignments.append({
                        "equipment_id":   eq.id,
                        "equipment_name": eq.name,
                        "equipment_type": eq.type,
                        "site_id":        s,
                        "site_name":      problem.site_names.get(s, s),
                        "day":            t,
                        "daily_cost":     eq.daily_rate,
                        "relocation_cost": reloc_cost,
                        "owned":          eq.owned,
                    })
                    total_rental += eq.daily_rate
                    equipment_used_days[eq.id] += 1
                    prev_site = s
                    break
            else:
                if (
                    (i, "_depot", t) in x
                    and solver.Value(x[i, "_depot", t]) == 1
                ):
                    prev_site = "_depot"

    # Collect unmet demand
    unmet_list: list[dict] = []
    total_penalty = 0.0
    for key, var in unmet.items():
        val = solver.Value(var)
        if val > 0:
            site_id, eq_type, day = key
            pen = val * problem.penalty_unmet
            total_penalty += pen
            unmet_list.append({
                "site_id":        site_id,
                "site_name":      problem.site_names.get(site_id, site_id),
                "equipment_type": eq_type,
                "day":            day,
                "shortfall":      val,
                "penalty":        pen,
            })

    _ASSIGN_COLS = [
        "equipment_id", "equipment_name", "equipment_type",
        "site_id", "site_name", "day",
        "daily_cost", "relocation_cost", "owned",
    ]
    _RELOC_COLS = [
        "equipment_id", "equipment_name",
        "from_site", "to_site", "day", "cost",
    ]
    _UNMET_COLS = [
        "site_id", "site_name", "equipment_type",
        "day", "shortfall", "penalty",
    ]

    df_assign = (
        pd.DataFrame(assignments) if assignments
        else pd.DataFrame(columns=_ASSIGN_COLS)
    )
    df_reloc = (
        pd.DataFrame(relocation_list) if relocation_list
        else pd.DataFrame(columns=_RELOC_COLS)
    )
    df_unmet = (
        pd.DataFrame(unmet_list) if unmet_list
        else pd.DataFrame(columns=_UNMET_COLS)
    )

    util_rows = []
    for eq in E:
        avail_days = eq.available_to - eq.available_from + 1
        used = equipment_used_days[eq.id]
        util_rows.append({
            "equipment_id":   eq.id,
            "equipment_name": eq.name,
            "equipment_type": eq.type,
            "owned":          eq.owned,
            "available_days": avail_days,
            "used_days":      used,
            "utilisation_pct": round(
                100 * used / max(avail_days, 1), 1
            ),
            "total_cost": eq.daily_rate * used,
        })
    df_util = pd.DataFrame(util_rows)

    objective_val = solver.ObjectiveValue() / SCALE
    total_cost = total_rental + total_relocation + total_penalty

    return FleetSolution(
        status="OPTIMAL" if status == cp_model.OPTIMAL else "FEASIBLE",
        objective=objective_val,
        assignments=df_assign,
        summary={
            "total_cost":      total_cost,
            "rental_cost":     total_rental,
            "relocation_cost": total_relocation,
            "penalty_cost":    total_penalty,
            "units_assigned": (
                len(set(df_assign["equipment_id"]))
                if len(df_assign) > 0 else 0
            ),
            "total_relocations": len(relocation_list),
            "unmet_demand_days": (
                int(df_unmet["shortfall"].sum())
                if len(df_unmet) > 0 else 0
            ),
            "avg_utilisation": (
                round(df_util["utilisation_pct"].mean(), 1)
                if len(df_util) > 0 else 0
            ),
        },
        relocations=df_reloc,
        unmet_demands=df_unmet,
        utilisation=df_util,
        cost_breakdown={
            "rental":     total_rental,
            "relocation": total_relocation,
            "penalty":    total_penalty,
        },
        solve_time=time.time() - t0,
    )
