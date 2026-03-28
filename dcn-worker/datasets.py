"""
Built-in demo datasets for ml_experiment tasks.

Generates large, realistic synthetic datasets at import time so there are
zero external dependencies (no CSV files, no network calls).

Datasets are sized to be genuinely compute-intensive for sklearn models
(50k-100k rows, 15+ features, polynomial interactions).
"""

import random
import math

# Seed for reproducible demo data
random.seed(42)


def _generate_weather_ri(n=75_000):
    """
    Synthetic Rhode Island weather dataset — HEAVY version.
    Target: temperature (F)
    15 features with nonlinear interactions to make models work harder.
    """
    rows = []
    for _ in range(n):
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        hour = random.randint(0, 23)
        base_temp = 30 + 25 * math.sin((month - 3) * math.pi / 6)

        # Time-of-day effect
        time_effect = 8 * math.sin((hour - 6) * math.pi / 12)

        cloud_cover = random.uniform(0, 100)
        humidity = random.uniform(20, 100)
        wind_speed = random.uniform(0, 35)
        wind_direction = random.uniform(0, 360)
        pressure = random.uniform(990, 1040)
        dew_point = base_temp - random.uniform(5, 25)
        precip_chance = min(100, max(0, humidity * 0.8 + cloud_cover * 0.3 - 30 + random.gauss(0, 10)))
        uv_index = max(0, (12 - abs(hour - 12)) * (1 - cloud_cover / 100) * random.uniform(0.5, 1.2))
        visibility = max(0.1, 10 - (humidity / 20) - (cloud_cover / 30) + random.gauss(0, 1))
        elevation = random.uniform(0, 250)  # RI elevation range in feet
        coastal_dist = random.uniform(0, 30)  # miles from coast
        prev_day_temp = base_temp + random.gauss(0, 5)
        soil_moisture = random.uniform(10, 90)

        # Complex nonlinear temperature model
        temperature = (
            base_temp
            + time_effect
            - cloud_cover * 0.08
            - wind_speed * 0.15
            + (pressure - 1013) * 0.12
            - (humidity - 60) * 0.04
            - elevation * 0.003  # lapse rate
            + coastal_dist * 0.05 * math.sin((month - 6) * math.pi / 6)  # coastal moderation
            + 0.3 * prev_day_temp * 0.1  # autocorrelation
            - soil_moisture * 0.02
            + wind_speed * math.cos(math.radians(wind_direction)) * 0.05  # wind direction effect
            + random.gauss(0, 3)
        )
        temperature = round(temperature, 2)

        rows.append({
            "month": month,
            "day": day,
            "hour": hour,
            "cloud_cover": round(cloud_cover, 2),
            "humidity": round(humidity, 2),
            "wind_speed": round(wind_speed, 2),
            "wind_direction": round(wind_direction, 2),
            "pressure": round(pressure, 2),
            "dew_point": round(dew_point, 2),
            "precip_chance": round(precip_chance, 2),
            "uv_index": round(uv_index, 2),
            "visibility": round(visibility, 2),
            "elevation": round(elevation, 2),
            "coastal_dist": round(coastal_dist, 2),
            "prev_day_temp": round(prev_day_temp, 2),
            "soil_moisture": round(soil_moisture, 2),
            "temperature": temperature,
        })
    return rows


def _generate_customer_churn(n=75_000):
    """
    Synthetic customer churn dataset — HEAVY version.
    Target: churn (0 or 1)
    12 features with interactions.
    """
    rows = []
    for _ in range(n):
        contract_type = random.choices([0, 1, 2], weights=[50, 30, 20])[0]
        payment_method = random.randint(0, 3)
        tenure = random.randint(1, 72)
        monthly_charges = round(random.uniform(18, 118), 2)
        total_charges = round(monthly_charges * tenure * random.uniform(0.85, 1.1), 2)
        num_products = random.randint(1, 6)
        has_internet = random.choices([0, 1], weights=[30, 70])[0]
        has_phone = random.choices([0, 1], weights=[20, 80])[0]
        tech_support_calls = random.randint(0, 15)
        online_security = random.choices([0, 1], weights=[55, 45])[0]
        paperless_billing = random.choices([0, 1], weights=[40, 60])[0]
        senior_citizen = random.choices([0, 1], weights=[85, 15])[0]

        # Complex churn model
        churn_score = (
            -0.03 * tenure
            + 0.015 * monthly_charges
            + (0.8 if contract_type == 0 else -0.3 if contract_type == 1 else -0.7)
            + (0.3 if payment_method == 0 else -0.1)
            - 0.1 * num_products
            + 0.15 * tech_support_calls
            - 0.3 * online_security
            + 0.2 * paperless_billing
            + 0.25 * senior_citizen
            + (0.2 if has_internet and not online_security else 0)  # internet without security
            - 0.01 * tenure * (1 if contract_type > 0 else 0)  # loyalty interaction
            + random.gauss(0, 0.5)
        )
        churn = 1 if churn_score > 0.5 else 0

        rows.append({
            "tenure": tenure,
            "monthly_charges": monthly_charges,
            "total_charges": total_charges,
            "contract_type": contract_type,
            "payment_method": payment_method,
            "num_products": num_products,
            "has_internet": has_internet,
            "has_phone": has_phone,
            "tech_support_calls": tech_support_calls,
            "online_security": online_security,
            "paperless_billing": paperless_billing,
            "senior_citizen": senior_citizen,
            "churn": churn,
        })
    return rows


# ── Dataset registry ──

DATASETS = {
    "weather_ri": {
        "generator": _generate_weather_ri,
        "target": "temperature",
        "task_category": "regression",
        "display_name": "Rhode Island Weather (75K rows)",
        "description": "Predict temperature from 16 weather/geographic features",
        "all_features": [
            "month", "day", "hour", "cloud_cover", "humidity", "wind_speed",
            "wind_direction", "pressure", "dew_point", "precip_chance",
            "uv_index", "visibility", "elevation", "coastal_dist",
            "prev_day_temp", "soil_moisture",
        ],
    },
    "customer_churn": {
        "generator": _generate_customer_churn,
        "target": "churn",
        "task_category": "classification",
        "display_name": "Customer Churn (75K rows)",
        "description": "Predict customer churn from 12 account/service features",
        "all_features": [
            "tenure", "monthly_charges", "total_charges", "contract_type",
            "payment_method", "num_products", "has_internet", "has_phone",
            "tech_support_calls", "online_security", "paperless_billing",
            "senior_citizen",
        ],
    },
}

# Cache generated data
_cache = {}


def get_dataset(name: str) -> tuple[list[dict], dict]:
    """
    Returns (rows, metadata) for a dataset name.
    Metadata includes: target, task_category, all_features, display_name, description.
    """
    if name not in DATASETS:
        raise ValueError(f"Unknown dataset: {name}. Available: {list(DATASETS.keys())}")

    if name not in _cache:
        info = DATASETS[name]
        _cache[name] = info["generator"]()

    info = DATASETS[name]
    meta = {k: v for k, v in info.items() if k != "generator"}
    return _cache[name], meta


def list_datasets() -> list[dict]:
    """List available datasets with metadata."""
    return [
        {"name": name, "display_name": info["display_name"],
         "description": info["description"], "task_category": info["task_category"],
         "target": info["target"], "features": info["all_features"]}
        for name, info in DATASETS.items()
    ]
