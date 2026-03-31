"""
Dataset loader for ml_experiment tasks.

Supports three sources:
  - built_in: synthetic datasets generated locally (zero network deps)
  - openml:   real-world datasets fetched via the OpenML API
  - csv_url:  any public CSV file fetched by URL

Built-in datasets are sized to be genuinely compute-intensive for sklearn
models (50k-100k rows, 15+ features, polynomial interactions).
"""

import random
import math
import csv
import io
import logging

logger = logging.getLogger("dcn.datasets")

MAX_ROWS = 100_000

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


# ── External dataset loading ──────────────────────────────────


_external_cache: dict[str, tuple[list[dict], dict]] = {}


def _infer_task_category(y_values: list, target_name: str) -> str:
    """Guess regression vs classification from target values."""
    unique = set(y_values[:5000])
    if len(unique) <= 30:
        return "classification"
    if all(isinstance(v, (int, float)) for v in list(unique)[:100]):
        return "regression"
    return "classification"


def _numeric_columns(rows: list[dict]) -> list[str]:
    """Return column names where all sampled values are numeric."""
    if not rows:
        return []
    sample = rows[:200]
    numeric = []
    for col in rows[0].keys():
        try:
            for r in sample:
                float(r[col])
            numeric.append(col)
        except (ValueError, TypeError, KeyError):
            continue
    return numeric


def _coerce_rows_numeric(rows: list[dict], features: list[str], target: str) -> list[dict]:
    """Convert feature + target values to float, dropping rows that fail."""
    cols = set(features) | {target}
    clean = []
    for r in rows:
        try:
            clean.append({c: float(r[c]) for c in cols})
        except (ValueError, TypeError, KeyError):
            continue
    return clean


def load_openml(dataset_id: str | int, target: str | None = None) -> tuple[list[dict], dict]:
    """Fetch a dataset from OpenML by numeric ID. Returns (rows, metadata).

    Non-numeric feature columns are label-encoded so classification datasets
    with mostly categorical inputs (e.g. monks-problems) still have usable features.
    """
    import pandas as pd
    import openml

    ds = openml.datasets.get_dataset(
        int(dataset_id),
        download_data=True,
        download_qualities=False,
        download_features_meta_data=True,
    )

    X, y, _, _ = ds.get_data(dataset_format="dataframe")

    default_t = ds.default_target_attribute
    if isinstance(default_t, list):
        default_t = default_t[0] if default_t else None
    resolved_target = target or default_t
    if resolved_target is None and len(X.columns):
        resolved_target = X.columns[-1]
    if resolved_target is None:
        raise ValueError(f"OpenML dataset {dataset_id} has no target column")

    if resolved_target in X.columns:
        df = X.copy()
    else:
        df = X.copy()
        df[resolved_target] = y

    if resolved_target not in df.columns:
        raise ValueError(
            f"Target column '{resolved_target}' not found in OpenML dataset {dataset_id}"
        )

    feature_cols = [c for c in df.columns if c != resolved_target]
    if not feature_cols:
        raise ValueError(f"OpenML dataset {dataset_id} has no feature columns")

    cache_key = f"openml:{dataset_id}:{resolved_target}"
    if cache_key in _external_cache:
        return _external_cache[cache_key]

    work = df[feature_cols + [resolved_target]].dropna(how="any")
    if work.empty:
        raise ValueError(f"OpenML dataset {dataset_id} has no rows after dropping NaNs")

    if len(work) > MAX_ROWS:
        work = work.sample(n=MAX_ROWS, random_state=42)

    # Infer regression vs classification from target (before encoding)
    y_series = work[resolved_target]
    if pd.api.types.is_numeric_dtype(y_series):
        y_vals = y_series.astype(float).tolist()[:5000]
    else:
        y_vals = pd.factorize(y_series)[0].tolist()[:5000]
    task_category = _infer_task_category(y_vals, resolved_target)

    # Encode categoricals so sklearn always sees numeric matrices
    work_enc = work.copy()
    for col in work_enc.columns:
        s = work_enc[col]
        if pd.api.types.is_numeric_dtype(s):
            work_enc[col] = s.astype(float)
        else:
            work_enc[col] = pd.factorize(s)[0].astype(float)

    rows = work_enc.to_dict("records")

    meta = {
        "target": resolved_target,
        "task_category": task_category,
        "all_features": feature_cols,
        "display_name": ds.name or f"OpenML #{dataset_id}",
        "description": (ds.description or "")[:200],
    }
    _external_cache[cache_key] = (rows, meta)
    return rows, meta


def load_csv_url(url: str, target: str | None = None) -> tuple[list[dict], dict]:
    """Download a CSV from a public URL. Returns (rows, metadata)."""
    cache_key = f"csv:{url}:{target}"
    if cache_key in _external_cache:
        return _external_cache[cache_key]

    import httpx

    resp = httpx.get(url, follow_redirects=True, timeout=60)
    resp.raise_for_status()

    text = resp.text
    reader = csv.DictReader(io.StringIO(text))
    all_rows = list(reader)
    if not all_rows:
        raise ValueError("CSV is empty or could not be parsed")

    numeric = _numeric_columns(all_rows)
    if not numeric:
        raise ValueError("CSV has no numeric columns")

    if target and target not in numeric:
        raise ValueError(f"Target '{target}' is not a numeric column. Numeric columns: {numeric}")

    if not target:
        target = numeric[-1]

    features = [c for c in numeric if c != target]
    if not features:
        raise ValueError("No feature columns remaining after selecting target")

    rows = _coerce_rows_numeric(all_rows, features, target)

    if len(rows) > MAX_ROWS:
        rows = random.sample(rows, MAX_ROWS)

    y_vals = [r[target] for r in rows]
    task_category = _infer_task_category(y_vals, target)

    meta = {
        "target": target,
        "task_category": task_category,
        "all_features": features,
        "display_name": url.split("/")[-1][:60] or "CSV Dataset",
        "description": f"{len(rows):,} rows, {len(features)} features",
    }
    _external_cache[cache_key] = (rows, meta)
    return rows, meta


def load_external_dataset(
    source: str, dataset_id: str, target: str | None = None
) -> tuple[list[dict], dict]:
    """Unified loader that dispatches by source type."""
    if source == "openml":
        return load_openml(dataset_id, target=target)
    elif source == "csv_url":
        return load_csv_url(dataset_id, target=target)
    elif source == "built_in":
        return get_dataset(dataset_id)
    else:
        raise ValueError(f"Unknown source: {source}")


def preview_dataset(
    source: str, dataset_id: str
) -> dict:
    """
    Fetch just enough info for the frontend preview:
    columns, row count, sample rows, suggested target + task category.
    """
    if source == "built_in":
        if dataset_id not in DATASETS:
            raise ValueError(f"Unknown built-in dataset: {dataset_id}")
        info = DATASETS[dataset_id]
        return {
            "columns": info["all_features"] + [info["target"]],
            "numeric_columns": info["all_features"] + [info["target"]],
            "row_count": 75_000,
            "sample_rows": [],
            "suggested_target": info["target"],
            "suggested_task_category": info["task_category"],
            "display_name": info["display_name"],
        }

    if source == "openml":
        import openml

        ds = openml.datasets.get_dataset(
            int(dataset_id),
            download_data=True,
            download_qualities=False,
            download_features_meta_data=True,
        )
        X, y, _, _ = ds.get_data(dataset_format="dataframe")
        target = ds.default_target_attribute or X.columns[-1]
        if target not in X.columns:
            X[target] = y
        numeric = list(X.select_dtypes(include=["number"]).columns)
        if target not in numeric:
            numeric.append(target)
        all_cols = list(X.columns)
        sample = X.head(5).to_dict("records")
        y_vals = X[target].dropna().tolist()[:5000]
        task_cat = _infer_task_category(y_vals, target)
        return {
            "columns": all_cols,
            "numeric_columns": numeric,
            "row_count": len(X),
            "sample_rows": sample,
            "suggested_target": target,
            "suggested_task_category": task_cat,
            "display_name": ds.name or f"OpenML #{dataset_id}",
        }

    if source == "csv_url":
        import httpx

        resp = httpx.get(dataset_id, follow_redirects=True, timeout=60)
        resp.raise_for_status()
        reader = csv.DictReader(io.StringIO(resp.text))
        all_rows = list(reader)
        if not all_rows:
            raise ValueError("CSV is empty")
        all_cols = list(all_rows[0].keys())
        numeric = _numeric_columns(all_rows)
        suggested_target = numeric[-1] if numeric else all_cols[-1]
        y_vals = []
        for r in all_rows[:5000]:
            try:
                y_vals.append(float(r[suggested_target]))
            except (ValueError, TypeError):
                pass
        task_cat = _infer_task_category(y_vals, suggested_target) if y_vals else "regression"
        sample = all_rows[:5]
        return {
            "columns": all_cols,
            "numeric_columns": numeric,
            "row_count": len(all_rows),
            "sample_rows": sample,
            "suggested_target": suggested_target,
            "suggested_task_category": task_cat,
            "display_name": dataset_id.split("/")[-1][:60] or "CSV",
        }

    raise ValueError(f"Unknown source: {source}")
