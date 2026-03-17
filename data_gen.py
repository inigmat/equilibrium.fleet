"""
equilibrium.fleet — Demo Data Generator
Generates realistic construction equipment fleet scenarios.
"""

import random
import numpy as np
from solver import Equipment, SiteDemand, FleetProblem

# Equipment type catalog
EQUIPMENT_CATALOG = {
    "excavator": {
        "names": [
            "CAT 320", "Komatsu PC200", "Volvo EC220",
            "Hitachi ZX200", "XCMG XE215",
        ],
        "daily_rate_owned": (80, 120),
        "daily_rate_rental": (150, 250),
        "relocation_cost": (300, 600),
        "capacity": (150, 300),
    },
    "dump_truck": {
        "names": [
            "KAMAZ 6520", "KAMAZ 65115", "Volvo FMX",
            "Scania P440", "MAN TGS",
        ],
        "daily_rate_owned": (50, 80),
        "daily_rate_rental": (100, 180),
        "relocation_cost": (50, 150),
        "capacity": (80, 160),
    },
    "concrete_pump": {
        "names": [
            "Putzmeister 36Z", "Schwing S39SX",
            "CIFA K41", "Sany SY5419THB",
        ],
        "daily_rate_owned": (120, 180),
        "daily_rate_rental": (250, 400),
        "relocation_cost": (200, 400),
        "capacity": (60, 120),
    },
    "crane_truck": {
        "names": [
            "Liebherr LTM 1060", "Tadano GR-300",
            "Zoomlion ZTC250", "XCMG QY25K",
        ],
        "daily_rate_owned": (150, 220),
        "daily_rate_rental": (300, 500),
        "relocation_cost": (400, 800),
        "capacity": (25, 60),
    },
    "loader": {
        "names": [
            "CAT 950M", "Volvo L120H", "Komatsu WA320",
            "JCB 456ZX", "XCMG LW500",
        ],
        "daily_rate_owned": (60, 100),
        "daily_rate_rental": (120, 200),
        "relocation_cost": (150, 300),
        "capacity": (100, 250),
    },
}

SITE_TEMPLATES = {
    "residential": {
        "names": [
            "Riverside Apartments", "Parkview Residences",
            "Central Heights", "Sunfield Estate", "Lakeview Complex",
        ],
        "demand_profile": {
            "excavator": (1, 2),
            "dump_truck": (2, 4),
            "concrete_pump": (1, 1),
            "crane_truck": (0, 1),
            "loader": (1, 2),
        },
    },
    "industrial": {
        "names": [
            "Logistics Warehouse", "Industrial Plant A",
            "Manufacturing Hub", "Cargo Terminal",
        ],
        "demand_profile": {
            "excavator": (2, 3),
            "dump_truck": (3, 6),
            "concrete_pump": (0, 1),
            "crane_truck": (1, 2),
            "loader": (2, 3),
        },
    },
    "infrastructure": {
        "names": [
            "Highway M-12 Sec.3", "River Bridge",
            "South Interchange", "Waterfront Phase 2",
        ],
        "demand_profile": {
            "excavator": (2, 4),
            "dump_truck": (4, 8),
            "concrete_pump": (1, 2),
            "crane_truck": (1, 2),
            "loader": (2, 4),
        },
    },
}


def generate_demo_scenario() -> FleetProblem:
    """Fixed demo scenario: 3 sites, 20-day horizon, 22 units."""
    random.seed(42)
    np.random.seed(42)

    horizon = 20
    sites_info = [
        ("S1", "Riverside Apartments", "residential"),
        ("S2", "Industrial Plant A", "industrial"),
        ("S3", "Highway M-12 Sec.3", "infrastructure"),
    ]

    # Generate equipment fleet
    equipment = []
    eq_id = 0

    fleet_spec = [
        ("excavator",     3, 2),
        ("dump_truck",    4, 3),
        ("concrete_pump", 1, 2),
        ("crane_truck",   1, 2),
        ("loader",        2, 2),
    ]

    for eq_type, n_owned, n_rental in fleet_spec:
        cat = EQUIPMENT_CATALOG[eq_type]
        names = cat["names"][:]
        random.shuffle(names)

        for j in range(n_owned):
            eq_id += 1
            equipment.append(Equipment(
                id=f"EQ-{eq_id:03d}",
                name=f"{names[j % len(names)]} #{eq_id}",
                type=eq_type,
                owned=True,
                daily_rate=random.randint(*cat["daily_rate_owned"]),
                relocation_cost=random.randint(*cat["relocation_cost"]),
                capacity=random.randint(*cat["capacity"]),
                available_from=0,
                available_to=horizon - 1,
            ))

        for j in range(n_rental):
            eq_id += 1
            avail_from = random.randint(0, 3)
            equipment.append(Equipment(
                id=f"EQ-{eq_id:03d}",
                name=f"{names[(n_owned + j) % len(names)]} (rental) #{eq_id}",
                type=eq_type,
                owned=False,
                daily_rate=random.randint(*cat["daily_rate_rental"]),
                relocation_cost=random.randint(*cat["relocation_cost"]),
                capacity=random.randint(*cat["capacity"]),
                available_from=avail_from,
                available_to=horizon - 1,
            ))

    # Generate demands with realistic patterns
    demands = []
    for site_id, site_name, site_type in sites_info:
        template = SITE_TEMPLATES[site_type]
        for eq_type, (lo, hi) in template["demand_profile"].items():
            base = random.randint(lo, hi)
            for day in range(horizon):
                wave = max(0, base + random.randint(-1, 1))
                # Some types not needed every day
                if eq_type == "concrete_pump" and day % 3 != 0:
                    wave = 0
                if eq_type == "crane_truck" and day % 2 != 0:
                    wave = max(0, wave - 1)
                if wave > 0:
                    demands.append(SiteDemand(
                        site_id=site_id,
                        site_name=site_name,
                        equipment_type=eq_type,
                        day=day,
                        quantity_needed=wave,
                        min_capacity=0,
                    ))

    site_ids = [s[0] for s in sites_info]
    site_names = {s[0]: s[1] for s in sites_info}

    return FleetProblem(
        equipment=equipment,
        demands=demands,
        horizon=horizon,
        sites=site_ids,
        site_names=site_names,
        penalty_unmet=500.0,
        max_relocations_per_unit=4,
    )


def generate_random_scenario(
    n_sites: int = 3,
    horizon: int = 20,
    fleet_size: int = 15,
    rental_fraction: float = 0.3,
    seed: int = 0,
) -> FleetProblem:
    """Generate a random scenario with given parameters."""
    random.seed(seed)
    np.random.seed(seed)

    all_types = list(SITE_TEMPLATES.keys())
    sites_info = []
    for i in range(n_sites):
        stype = random.choice(all_types)
        template = SITE_TEMPLATES[stype]
        name = random.choice(template["names"])
        sites_info.append((f"S{i+1}", f"{name} #{i+1}", stype))

    # Generate fleet
    equipment = []
    eq_types = list(EQUIPMENT_CATALOG.keys())
    per_type = max(1, fleet_size // len(eq_types))

    eq_id = 0
    for eq_type in eq_types:
        cat = EQUIPMENT_CATALOG[eq_type]
        n_total = per_type + random.randint(-1, 1)
        n_total = max(1, n_total)
        n_rental = max(0, int(n_total * rental_fraction))
        n_owned = n_total - n_rental
        names = cat["names"][:]

        for j in range(n_owned):
            eq_id += 1
            equipment.append(Equipment(
                id=f"EQ-{eq_id:03d}",
                name=f"{names[j % len(names)]} #{eq_id}",
                type=eq_type,
                owned=True,
                daily_rate=random.randint(*cat["daily_rate_owned"]),
                relocation_cost=random.randint(*cat["relocation_cost"]),
                capacity=random.randint(*cat["capacity"]),
                available_from=0,
                available_to=horizon - 1,
            ))
        for j in range(n_rental):
            eq_id += 1
            equipment.append(Equipment(
                id=f"EQ-{eq_id:03d}",
                name=f"{names[(n_owned + j) % len(names)]} (rental) #{eq_id}",
                type=eq_type,
                owned=False,
                daily_rate=random.randint(*cat["daily_rate_rental"]),
                relocation_cost=random.randint(*cat["relocation_cost"]),
                capacity=random.randint(*cat["capacity"]),
                available_from=random.randint(0, min(3, horizon - 1)),
                available_to=horizon - 1,
            ))

    # Generate demands
    demands = []
    for site_id, site_name, site_type in sites_info:
        template = SITE_TEMPLATES[site_type]
        for eq_type, (lo, hi) in template["demand_profile"].items():
            base = random.randint(lo, hi)
            for day in range(horizon):
                wave = max(0, base + random.randint(-1, 1))
                if wave > 0:
                    demands.append(SiteDemand(
                        site_id=site_id,
                        site_name=site_name,
                        equipment_type=eq_type,
                        day=day,
                        quantity_needed=wave,
                        min_capacity=0,
                    ))

    site_ids = [s[0] for s in sites_info]
    site_names_map = {s[0]: s[1] for s in sites_info}

    return FleetProblem(
        equipment=equipment,
        demands=demands,
        horizon=horizon,
        sites=site_ids,
        site_names=site_names_map,
        penalty_unmet=500.0,
        max_relocations_per_unit=4,
    )
