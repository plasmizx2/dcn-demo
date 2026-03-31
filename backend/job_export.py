"""Build downloadable exports (CSV, JSON payload) from ML experiment task results."""

import csv
import io
import json
import re
from typing import Any


def safe_export_filename(title: str | None, job_id: str, ext: str) -> str:
    raw = (title or "job").strip() or "job"
    base = re.sub(r"[^\w\-.]+", "_", raw)[:50].strip("_") or "job"
    short_id = str(job_id).replace("-", "")[:8]
    return f"dcn_{base}_{short_id}.{ext}"


def experiments_to_csv(experiments: list[dict[str, Any]]) -> str:
    """Ranked rows; same metric ordering as the aggregator report."""
    if not experiments:
        return "message\nno_parsed_experiment_metrics_in_results\n"

    cat = experiments[0].get("task_category", "regression")
    buf = io.StringIO()

    if cat == "regression":
        fieldnames = [
            "rank",
            "model_type",
            "model_display",
            "r2",
            "cv_r2_mean",
            "cv_r2_std",
            "mse",
            "mae",
            "total_time_seconds",
            "n_features",
        ]
    else:
        fieldnames = [
            "rank",
            "model_type",
            "model_display",
            "f1",
            "accuracy",
            "precision",
            "recall",
            "cv_f1_mean",
            "cv_f1_std",
            "total_time_seconds",
            "n_features",
        ]

    w = csv.DictWriter(buf, fieldnames=fieldnames)
    w.writeheader()
    for i, exp in enumerate(experiments, 1):
        row: dict[str, Any] = {"rank": i, "n_features": len(exp.get("features") or [])}
        for k in fieldnames:
            if k in ("rank", "n_features"):
                continue
            v = exp.get(k)
            row[k] = "" if v is None else v
        w.writerow({k: row.get(k, "") for k in fieldnames})

    return buf.getvalue()


def build_json_export(
    job: dict,
    experiments: list[dict[str, Any]],
    ranked: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "job_id": str(job.get("id", "")),
        "title": job.get("title"),
        "task_type": job.get("task_type"),
        "status": job.get("status"),
        "created_at": job.get("created_at").isoformat() if job.get("created_at") else None,
        "experiments_ranked": ranked,
        "experiments_raw_count": len(experiments),
        "markdown_report": job.get("final_output"),
        "export_note": "experiments_ranked matches the comparison table in the markdown report",
    }


def json_dumps_export(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, default=str)
