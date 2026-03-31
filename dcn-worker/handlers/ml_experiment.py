"""Local worker handler for ml_experiment — trains sklearn models with cross-validation."""

import time
import json
from resource_guard import safe_n_jobs, safe_dataset_size


def handle(task: dict, job: dict) -> str:
    from sklearn.model_selection import train_test_split, cross_validate
    from sklearn.metrics import (
        r2_score, mean_squared_error, mean_absolute_error,
        accuracy_score, f1_score, precision_score, recall_score,
    )
    from sklearn.linear_model import LinearRegression, Ridge, LogisticRegression
    from sklearn.tree import DecisionTreeRegressor, DecisionTreeClassifier
    from sklearn.ensemble import (
        RandomForestRegressor, RandomForestClassifier,
        GradientBoostingRegressor, GradientBoostingClassifier,
    )
    import numpy as np
    from datasets import get_dataset, load_external_dataset

    payload = task.get("task_payload", {})
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {}

    experiment_type = payload.get("experiment_type", "linear_regression")
    dataset_name = payload.get("dataset_name", "weather_ri")
    target = payload.get("target", "temperature")
    task_category = payload.get("task_category", "regression")
    features = payload.get("features")
    cv_folds = payload.get("cv_folds", 5)
    params = payload.get("params", {})

    source = payload.get("source", "built_in")
    dataset_id = payload.get("dataset_id", "")

    if source in ("openml", "csv_url") and dataset_id:
        rows, meta = load_external_dataset(source, dataset_id, target=target)
        target = meta["target"]
        task_category = meta["task_category"]
    else:
        rows, meta = get_dataset(dataset_name)

    if not features:
        features = meta["all_features"]

    # Limit dataset size based on available RAM to prevent crashes
    max_rows = safe_dataset_size(len(rows))
    if max_rows < len(rows):
        import random
        rows = random.sample(rows, max_rows)

    X = np.array([[row[f] for f in features] for row in rows])
    y = np.array([row[target] for row in rows])

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42
    )

    MODEL_MAP = {
        "linear_regression": lambda p: LinearRegression(),
        "ridge_regression": lambda p: Ridge(alpha=p.get("alpha", 1.0)),
        "decision_tree_regressor": lambda p: DecisionTreeRegressor(
            max_depth=p.get("max_depth", 5), random_state=42),
        "random_forest_regressor": lambda p: RandomForestRegressor(
            n_estimators=p.get("n_estimators", 100),
            max_depth=p.get("max_depth", 10), random_state=42, n_jobs=safe_n_jobs()),
        "gradient_boosting_regressor": lambda p: GradientBoostingRegressor(
            n_estimators=p.get("n_estimators", 200),
            max_depth=p.get("max_depth", 5),
            learning_rate=p.get("learning_rate", 0.1), random_state=42),
        "logistic_regression": lambda p: LogisticRegression(
            max_iter=p.get("max_iter", 2000), random_state=42),
        "logistic_regression_l1": lambda p: LogisticRegression(
            penalty="l1", solver="saga",
            max_iter=p.get("max_iter", 2000),
            C=p.get("C", 0.5), random_state=42),
        "decision_tree_classifier": lambda p: DecisionTreeClassifier(
            max_depth=p.get("max_depth", 5), random_state=42),
        "random_forest_classifier": lambda p: RandomForestClassifier(
            n_estimators=p.get("n_estimators", 100),
            max_depth=p.get("max_depth", 10), random_state=42, n_jobs=safe_n_jobs()),
        "gradient_boosting_classifier": lambda p: GradientBoostingClassifier(
            n_estimators=p.get("n_estimators", 200),
            max_depth=p.get("max_depth", 5),
            learning_rate=p.get("learning_rate", 0.1), random_state=42),
    }

    model_factory = MODEL_MAP.get(experiment_type)
    if not model_factory:
        return f"Unknown experiment type: {experiment_type}"

    model = model_factory(params)

    # Cross-validation (the heavy part)
    cv_start = time.time()
    if task_category == "regression":
        cv_scoring = ["r2", "neg_mean_squared_error", "neg_mean_absolute_error"]
    else:
        cv_scoring = ["accuracy", "f1_weighted", "precision_weighted", "recall_weighted"]

    cv_results = cross_validate(
        model, X_train, y_train,
        cv=cv_folds, scoring=cv_scoring,
        return_train_score=True, n_jobs=safe_n_jobs(),
    )
    cv_time = round(time.time() - cv_start, 3)

    # Final fit + test eval
    train_start = time.time()
    model.fit(X_train, y_train)
    train_time = round(time.time() - train_start, 3)

    y_pred = model.predict(X_test)

    if task_category == "regression":
        r2 = round(r2_score(y_test, y_pred), 4)
        mse = round(mean_squared_error(y_test, y_pred), 4)
        mae = round(mean_absolute_error(y_test, y_pred), 4)
        cv_r2_mean = round(float(np.mean(cv_results["test_r2"])), 4)
        cv_r2_std = round(float(np.std(cv_results["test_r2"])), 4)
        cv_mse_mean = round(float(-np.mean(cv_results["test_neg_mean_squared_error"])), 4)
        primary_metric_name = "r2"
        primary_metric_value = r2
        metrics_text = (
            f"- **R² Score:** {r2}\n- **MSE:** {mse}\n- **MAE:** {mae}\n"
            f"- **CV R² (mean +/- std):** {cv_r2_mean} +/- {cv_r2_std}\n"
            f"- **CV MSE (mean):** {cv_mse_mean}"
        )
        metrics_json = {"r2": r2, "mse": mse, "mae": mae,
                        "cv_r2_mean": cv_r2_mean, "cv_r2_std": cv_r2_std, "cv_mse_mean": cv_mse_mean}
    else:
        acc = round(accuracy_score(y_test, y_pred), 4)
        f1 = round(f1_score(y_test, y_pred, average="weighted"), 4)
        prec = round(precision_score(y_test, y_pred, average="weighted"), 4)
        rec = round(recall_score(y_test, y_pred, average="weighted"), 4)
        cv_f1_mean = round(float(np.mean(cv_results["test_f1_weighted"])), 4)
        cv_f1_std = round(float(np.std(cv_results["test_f1_weighted"])), 4)
        cv_acc_mean = round(float(np.mean(cv_results["test_accuracy"])), 4)
        primary_metric_name = "f1"
        primary_metric_value = f1
        metrics_text = (
            f"- **Accuracy:** {acc}\n- **F1 Score:** {f1}\n"
            f"- **Precision:** {prec}\n- **Recall:** {rec}\n"
            f"- **CV F1 (mean +/- std):** {cv_f1_mean} +/- {cv_f1_std}\n"
            f"- **CV Accuracy (mean):** {cv_acc_mean}"
        )
        metrics_json = {"accuracy": acc, "f1": f1, "precision": prec, "recall": rec,
                        "cv_f1_mean": cv_f1_mean, "cv_f1_std": cv_f1_std, "cv_acc_mean": cv_acc_mean}

    model_display = type(model).__name__
    params_display = ", ".join(f"{k}={v}" for k, v in params.items()) if params else "defaults"
    total_time = round(cv_time + train_time, 3)

    result_data = {
        "model_type": experiment_type,
        "model_display": model_display,
        "dataset_name": dataset_name,
        "target": target,
        "task_category": task_category,
        "features": features,
        "params": params,
        "cv_folds": cv_folds,
        "primary_metric_name": primary_metric_name,
        "primary_metric_value": primary_metric_value,
        "cv_time_seconds": cv_time,
        "train_time_seconds": train_time,
        "total_time_seconds": total_time,
        "n_train": len(X_train),
        "n_test": len(X_test),
        "n_total": len(X),
        **metrics_json,
    }

    summary = (
        f"## Experiment: {model_display}\n\n"
        f"**Model:** {model_display}({params_display})\n"
        f"**Dataset:** {meta.get('display_name', dataset_name)} -> {target}\n"
        f"**Features:** {len(features)} ({', '.join(features[:5])}{'...' if len(features) > 5 else ''})\n"
        f"**Samples:** {len(X):,} total ({len(X_train):,} train / {len(X_test):,} test)\n"
        f"**Cross-Validation:** {cv_folds}-fold\n"
        f"**CV Time:** {cv_time}s | **Train Time:** {train_time}s | **Total:** {total_time}s\n\n"
        f"### Metrics\n{metrics_text}\n\n"
        f"```json\n{json.dumps(result_data, indent=2)}\n```"
    )

    return summary
