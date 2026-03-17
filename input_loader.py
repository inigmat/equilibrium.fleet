"""
equilibrium.fleet — Input Loader
Handles Excel template generation, file parsing, and manual input building.
"""

import io
import pandas as pd
from solver import Equipment, SiteDemand, FleetProblem

EQUIPMENT_TYPES = [
    "excavator", "dump_truck", "concrete_pump", "crane_truck", "loader",
]

EQUIPMENT_TYPE_LABELS_RU = {
    "excavator":     "Excavator",
    "dump_truck":    "Dump Truck",
    "concrete_pump": "Concrete Pump",
    "crane_truck":   "Crane Truck",
    "loader":        "Loader",
}

_TYPE_FROM_LABEL = {v: k for k, v in EQUIPMENT_TYPE_LABELS_RU.items()}

# ── Default rows for manual editor ───────────────────────────────────────────

DEFAULT_EQUIPMENT_DF = pd.DataFrame([
    {
        "id": "EQ-001", "name": "CAT 320 #1",
        "type": "excavator", "owned": True,
        "daily_rate": 90, "relocation_cost": 450,
        "capacity": 200, "available_from": 0, "available_to": 19,
    },
    {
        "id": "EQ-002", "name": "KAMAZ 6520 #2",
        "type": "dump_truck", "owned": True,
        "daily_rate": 60, "relocation_cost": 100,
        "capacity": 120, "available_from": 0, "available_to": 19,
    },
    {
        "id": "EQ-003", "name": "KAMAZ 65115 #3",
        "type": "dump_truck", "owned": True,
        "daily_rate": 55, "relocation_cost": 100,
        "capacity": 110, "available_from": 0, "available_to": 19,
    },
    {
        "id": "EQ-004", "name": "Putzmeister 36Z (rental) #4",
        "type": "concrete_pump", "owned": False,
        "daily_rate": 300, "relocation_cost": 300,
        "capacity": 90, "available_from": 2, "available_to": 19,
    },
    {
        "id": "EQ-005", "name": "Liebherr LTM (rental) #5",
        "type": "crane_truck", "owned": False,
        "daily_rate": 350, "relocation_cost": 600,
        "capacity": 40, "available_from": 0, "available_to": 19,
    },
    {
        "id": "EQ-006", "name": "CAT 950M #6",
        "type": "loader", "owned": True,
        "daily_rate": 70, "relocation_cost": 200,
        "capacity": 170, "available_from": 0, "available_to": 19,
    },
])

DEFAULT_DEMAND_DF = pd.DataFrame([
    {
        "site_id": "S1", "site_name": "Riverside Apartments",
        "equipment_type": "excavator",
        "day_from": 0, "day_to": 4,
        "quantity_needed": 1, "min_capacity": 0,
    },
    {
        "site_id": "S1", "site_name": "Riverside Apartments",
        "equipment_type": "dump_truck",
        "day_from": 0, "day_to": 4,
        "quantity_needed": 2, "min_capacity": 0,
    },
    {
        "site_id": "S1", "site_name": "Riverside Apartments",
        "equipment_type": "concrete_pump",
        "day_from": 0, "day_to": 4,
        "quantity_needed": 1, "min_capacity": 0,
    },
    {
        "site_id": "S2", "site_name": "Industrial Plant A",
        "equipment_type": "excavator",
        "day_from": 2, "day_to": 9,
        "quantity_needed": 1, "min_capacity": 0,
    },
    {
        "site_id": "S2", "site_name": "Industrial Plant A",
        "equipment_type": "dump_truck",
        "day_from": 2, "day_to": 9,
        "quantity_needed": 1, "min_capacity": 0,
    },
    {
        "site_id": "S2", "site_name": "Industrial Plant A",
        "equipment_type": "crane_truck",
        "day_from": 5, "day_to": 14,
        "quantity_needed": 1, "min_capacity": 0,
    },
])


# ── Excel template ───────────────────────────────────────────────────────────

def get_excel_template_bytes() -> bytes:
    """Generate a downloadable Excel template with example data."""
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        DEFAULT_EQUIPMENT_DF.to_excel(
            writer, sheet_name="Equipment", index=False,
        )
        DEFAULT_DEMAND_DF.to_excel(
            writer, sheet_name="Demand", index=False,
        )

        # Column reference for Equipment sheet
        ref_eq = pd.DataFrame({
            "Column": [
                "id", "name", "type", "owned",
                "daily_rate", "relocation_cost", "capacity",
                "available_from", "available_to",
            ],
            "Description": [
                "Unique identifier (e.g. EQ-001)",
                "Equipment display name",
                "Type — must match values in Equipment_Types sheet",
                "TRUE = company-owned, FALSE = rental",
                "Daily rate, $",
                "Relocation cost per move, $",
                "Productivity (units/day)",
                "First available day (0 = first planning day)",
                "Last available day (inclusive)",
            ],
        })
        ref_eq.to_excel(
            writer, sheet_name="Reference_Equipment", index=False,
        )

        # Column reference for Demand sheet
        ref_dem = pd.DataFrame({
            "Column": [
                "site_id", "site_name", "equipment_type",
                "day_from", "day_to",
                "quantity_needed", "min_capacity",
            ],
            "Description": [
                "Site identifier (S1, S2, ...)",
                "Site display name",
                "Equipment type — must match Equipment_Types sheet",
                "First day of demand (0 = first planning day)",
                "Last day of demand (inclusive)",
                "Number of units required per day",
                "Minimum productivity threshold (0 = not set)",
            ],
        })
        ref_dem.to_excel(
            writer, sheet_name="Reference_Demand", index=False,
        )

        # Valid equipment types
        types_df = pd.DataFrame({
            "type (use in Excel)": list(EQUIPMENT_TYPES),
            "Label":               list(EQUIPMENT_TYPE_LABELS_RU.values()),
        })
        types_df.to_excel(
            writer, sheet_name="Equipment_Types", index=False,
        )

    return output.getvalue()


# ── Helpers ──────────────────────────────────────────────────────────────────

def _expand_demand_range(
    site_id: str,
    site_name: str,
    eq_type: str,
    day_from: int,
    day_to: int,
    qty: int,
    min_cap: float,
) -> list[SiteDemand]:
    """Expand a day range into individual SiteDemand records."""
    return [
        SiteDemand(
            site_id=site_id,
            site_name=site_name,
            equipment_type=eq_type,
            day=d,
            quantity_needed=qty,
            min_capacity=min_cap,
        )
        for d in range(day_from, day_to + 1)
    ]


def _resolve_eq_type(raw: str) -> str | None:
    """Resolve equipment type key from English key or label string."""
    s = str(raw).strip()
    if s in EQUIPMENT_TYPES:
        return s
    label_match = _TYPE_FROM_LABEL.get(s)
    if label_match:
        return label_match
    s_lower = s.lower()
    if s_lower in EQUIPMENT_TYPES:
        return s_lower
    for k, v in EQUIPMENT_TYPE_LABELS_RU.items():
        if v.lower() == s_lower:
            return k
    return None


def parse_excel_to_problem(
    file,
    penalty: float = 500.0,
    max_reloc: int = 4,
) -> tuple[FleetProblem, list[str]]:
    """
    Parse an uploaded Excel file and return (FleetProblem, warnings).
    Raises ValueError on critical errors.
    """
    warnings: list[str] = []

    try:
        xl = pd.read_excel(file, sheet_name=None)
    except Exception as e:
        raise ValueError(f"Could not read Excel file: {e}")

    # ── Find Equipment sheet ───────────────────────────────────────────────
    sheet_eq = None
    for name, df in xl.items():
        if name.lower() in ("equipment", "fleet", "техника"):
            sheet_eq = df
            break
    if sheet_eq is None:
        raise ValueError(
            "Sheet 'Equipment' not found. "
            "Please use the template (Download Template button)."
        )

    required_eq = {
        "id", "name", "type", "owned", "daily_rate",
        "relocation_cost", "capacity", "available_from", "available_to",
    }
    missing = required_eq - set(sheet_eq.columns)
    if missing:
        raise ValueError(
            f"Equipment sheet is missing columns: {', '.join(sorted(missing))}"
        )

    equipment: list[Equipment] = []
    for i, row in sheet_eq.iterrows():
        eq_type = _resolve_eq_type(row["type"])
        if eq_type is None:
            warnings.append(
                f"Equipment row {i+2}: unknown type '{row['type']}' — skipped"
            )
            continue
        try:
            equipment.append(Equipment(
                id=str(row["id"]).strip(),
                name=str(row["name"]).strip(),
                type=eq_type,
                owned=bool(row["owned"]),
                daily_rate=float(row["daily_rate"]),
                relocation_cost=float(row["relocation_cost"]),
                capacity=float(row["capacity"]),
                available_from=int(row["available_from"]),
                available_to=int(row["available_to"]),
            ))
        except Exception as e:
            warnings.append(f"Equipment row {i+2}: parse error — {e}")

    if not equipment:
        raise ValueError("No valid equipment rows found.")

    # ── Find Demand sheet ──────────────────────────────────────────────────
    sheet_dem = None
    for name, df in xl.items():
        if name.lower() in ("demand", "demands", "спрос"):
            sheet_dem = df
            break
    if sheet_dem is None:
        raise ValueError(
            "Sheet 'Demand' not found. "
            "Please use the template (Download Template button)."
        )

    cols = set(sheet_dem.columns)
    has_range = "day_from" in cols and "day_to" in cols
    required_dem = {
        "site_id", "site_name", "equipment_type", "quantity_needed",
    } | ({"day_from", "day_to"} if has_range else {"day"})
    missing = required_dem - cols
    if missing:
        raise ValueError(
            f"Demand sheet is missing columns: {', '.join(sorted(missing))}"
        )

    demands: list[SiteDemand] = []
    for i, row in sheet_dem.iterrows():
        eq_type = _resolve_eq_type(row["equipment_type"])
        if eq_type is None:
            warnings.append(
                f"Demand row {i+2}: unknown type "
                f"'{row['equipment_type']}' — skipped"
            )
            continue
        try:
            qty = int(row["quantity_needed"])
        except Exception:
            warnings.append(
                f"Demand row {i+2}: invalid quantity_needed — skipped"
            )
            continue
        if qty <= 0:
            continue
        try:
            site_id = str(row["site_id"]).strip()
            site_name = str(row["site_name"]).strip()
            min_cap = float(row.get("min_capacity", 0) or 0)
            if has_range:
                day_from = int(row["day_from"])
                day_to = int(row["day_to"])
            else:
                day_from = day_to = int(row["day"])
            demands.extend(_expand_demand_range(
                site_id, site_name, eq_type,
                day_from, day_to, qty, min_cap,
            ))
        except Exception as e:
            warnings.append(f"Demand row {i+2}: parse error — {e}")

    if not demands:
        raise ValueError("No valid demand rows found.")

    return _build_problem(equipment, demands, penalty, max_reloc), warnings


def build_problem_from_manual(
    eq_df: pd.DataFrame,
    dem_df: pd.DataFrame,
    penalty: float = 500.0,
    max_reloc: int = 4,
) -> tuple[FleetProblem, list[str]]:
    """Build FleetProblem from data_editor DataFrames (manual input)."""
    warnings: list[str] = []

    equipment: list[Equipment] = []
    for i, row in eq_df.iterrows():
        eq_type = _resolve_eq_type(row.get("type", ""))
        if eq_type is None:
            warnings.append(
                f"Equipment row {i+1}: unknown type "
                f"'{row.get('type', '')}' — skipped"
            )
            continue
        try:
            raw_id = str(row.get("id", "")).strip()
            equipment.append(Equipment(
                id=raw_id if raw_id else f"EQ-{i+1:03d}",
                name=str(row["name"]).strip(),
                type=eq_type,
                owned=bool(row["owned"]),
                daily_rate=float(row["daily_rate"]),
                relocation_cost=float(row["relocation_cost"]),
                capacity=float(row["capacity"]),
                available_from=int(row["available_from"]),
                available_to=int(row["available_to"]),
            ))
        except Exception as e:
            warnings.append(f"Equipment row {i+1}: error — {e}")

    if not equipment:
        raise ValueError(
            "No equipment found. Please fill in the Equipment table."
        )

    dem_cols = set(dem_df.columns)
    has_range = "day_from" in dem_cols and "day_to" in dem_cols

    demands: list[SiteDemand] = []
    for i, row in dem_df.iterrows():
        eq_type = _resolve_eq_type(row.get("equipment_type", ""))
        if eq_type is None:
            warnings.append(f"Demand row {i+1}: unknown type — skipped")
            continue
        try:
            qty = int(row["quantity_needed"])
        except Exception:
            continue
        if qty <= 0:
            continue
        try:
            site_id = str(row["site_id"]).strip()
            site_name = str(row["site_name"]).strip()
            min_cap = float(row.get("min_capacity", 0) or 0)
            if has_range:
                day_from = int(row["day_from"])
                day_to = int(row["day_to"])
            else:
                day_from = day_to = int(row["day"])
            demands.extend(_expand_demand_range(
                site_id, site_name, eq_type,
                day_from, day_to, qty, min_cap,
            ))
        except Exception as e:
            warnings.append(f"Demand row {i+1}: error — {e}")

    if not demands:
        raise ValueError(
            "No demand rows found. Please fill in the Demand table."
        )

    return _build_problem(equipment, demands, penalty, max_reloc), warnings


# ── Internal ─────────────────────────────────────────────────────────────────

def _build_problem(
    equipment: list[Equipment],
    demands: list[SiteDemand],
    penalty: float,
    max_reloc: int,
) -> FleetProblem:
    horizon = max(d.day for d in demands) + 1
    for eq in equipment:
        eq.available_to = min(eq.available_to, horizon - 1)
        eq.available_from = max(0, eq.available_from)

    site_ids = sorted({d.site_id for d in demands})
    site_names: dict[str, str] = {}
    for d in demands:
        site_names[d.site_id] = d.site_name

    return FleetProblem(
        equipment=equipment,
        demands=demands,
        horizon=horizon,
        sites=site_ids,
        site_names=site_names,
        penalty_unmet=penalty,
        max_relocations_per_unit=max_reloc,
    )
