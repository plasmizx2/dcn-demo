"""
Planner module — splits a job into subtasks based on task_type.

Currently focused on ml_experiment: generates multiple experiment
configurations with different models and hyperparameters so workers
can train and evaluate them in parallel.
"""


def plan_tasks(task_type: str, input_payload: dict) -> list[dict]:
    """
    Given a task_type and the job's input_payload, return a list of subtask dicts.
    Each dict has: task_name, task_description, task_payload
    """

    if task_type == "ml_experiment":
        return _plan_ml_experiment(input_payload)

    else:
        return [
            {"task_name": f"step_{i}", "task_description": f"Subtask {i} for {task_type}", "task_payload": {}}
            for i in range(1, 4)
        ]


def _plan_ml_experiment(input_payload: dict) -> list[dict]:
    """
    Generate heavy ML experiment subtasks — each trains a different model/config
    with cross-validation. Supports built-in, OpenML, and CSV URL datasets.
    """
    source = input_payload.get("source", "built_in")
    dataset_id = input_payload.get("dataset_id", "")
    dataset_name = input_payload.get("dataset_name", "weather_ri")

    if source in ("openml", "csv_url", "csv_upload") and dataset_id:
        from datasets import load_external_dataset
        target_override = input_payload.get("target")
        _, meta = load_external_dataset(source, dataset_id, target=target_override)
        target = meta["target"]
        task_category = meta["task_category"]
        all_features = meta["all_features"]
    else:
        source = "built_in"
        from datasets import DATASETS
        ds_info = DATASETS.get(dataset_name, DATASETS["weather_ri"])
        target = ds_info["target"]
        task_category = ds_info["task_category"]
        all_features = ds_info["all_features"]

    reduced_features = all_features[:5]
    mid_features = all_features[:len(all_features) // 2]

    display_name = dataset_name if source == "built_in" else dataset_id

    base = {
        "source": source,
        "dataset_id": dataset_id,
        "dataset_name": dataset_name,
        "target": target,
        "task_category": task_category,
    }

    if task_category == "regression":
        return [
            {
                "task_name": "experiment_linear_baseline",
                "task_description": f"5-fold CV LinearRegression on {display_name} (all features)",
                "task_payload": {**base, "experiment_type": "linear_regression", "features": all_features, "cv_folds": 5, "params": {}, "min_tier": 2},
            },
            {
                "task_name": "experiment_ridge_regression",
                "task_description": f"5-fold CV Ridge (alpha=1.0) on {display_name}",
                "task_payload": {**base, "experiment_type": "ridge_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 1.0}, "min_tier": 2},
            },
            {
                "task_name": "experiment_decision_tree_deep",
                "task_description": f"5-fold CV DecisionTree (max_depth=15) on {display_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_regressor", "features": all_features, "cv_folds": 5, "params": {"max_depth": 15}, "min_tier": 2},
            },
            {
                "task_name": "experiment_random_forest_medium",
                "task_description": f"5-fold CV RandomForest (200 trees, depth=10) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 3},
            },
            {
                "task_name": "experiment_random_forest_heavy",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 3},
            },
            {
                "task_name": "experiment_gradient_boosting",
                "task_description": f"5-fold CV GradientBoosting (200 trees, depth=5, lr=0.1) on {display_name}",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1}, "min_tier": 3},
            },
            {
                "task_name": "experiment_feature_reduced",
                "task_description": f"5-fold CV RandomForest with reduced features ({', '.join(reduced_features)})",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": reduced_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 2},
            },
            {
                "task_name": "experiment_gb_tuned",
                "task_description": f"5-fold CV GradientBoosting tuned (500 trees, depth=8, lr=0.05)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 8, "learning_rate": 0.05}, "min_tier": 3},
            },
            # ── New model families ──
            {
                "task_name": "experiment_lasso",
                "task_description": f"5-fold CV Lasso (alpha=1.0) on {display_name}",
                "task_payload": {**base, "experiment_type": "lasso_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 1.0}, "min_tier": 2},
            },
            {
                "task_name": "experiment_elasticnet",
                "task_description": f"5-fold CV ElasticNet (alpha=0.5, l1_ratio=0.5) on {display_name}",
                "task_payload": {**base, "experiment_type": "elasticnet_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 0.5, "l1_ratio": 0.5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_knn_regressor",
                "task_description": f"5-fold CV KNeighbors (k=5) on {display_name}",
                "task_payload": {**base, "experiment_type": "knn_regressor", "features": all_features, "cv_folds": 5, "params": {"n_neighbors": 5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_extra_trees",
                "task_description": f"5-fold CV ExtraTrees (300 trees, depth=15) on {display_name}",
                "task_payload": {**base, "experiment_type": "extra_trees_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 300, "max_depth": 15}, "min_tier": 3},
            },
            {
                "task_name": "experiment_adaboost",
                "task_description": f"5-fold CV AdaBoost (200 estimators, lr=0.1) on {display_name}",
                "task_payload": {**base, "experiment_type": "adaboost_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "learning_rate": 0.1}, "min_tier": 3},
            },
            # ── Hyperparameter variants ──
            {
                "task_name": "experiment_ridge_low_alpha",
                "task_description": f"5-fold CV Ridge (alpha=0.1) on {display_name}",
                "task_payload": {**base, "experiment_type": "ridge_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 0.1}, "min_tier": 2},
            },
            {
                "task_name": "experiment_ridge_high_alpha",
                "task_description": f"5-fold CV Ridge (alpha=10.0) on {display_name}",
                "task_payload": {**base, "experiment_type": "ridge_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 10.0}, "min_tier": 2},
            },
            {
                "task_name": "experiment_decision_tree_shallow",
                "task_description": f"5-fold CV DecisionTree (max_depth=5) on {display_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_regressor", "features": all_features, "cv_folds": 5, "params": {"max_depth": 5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_gb_stochastic",
                "task_description": f"5-fold CV GradientBoosting stochastic (subsample=0.8) on {display_name}",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1, "subsample": 0.8}, "min_tier": 3},
            },
            {
                "task_name": "experiment_rf_sqrt_features",
                "task_description": f"5-fold CV RandomForest (200 trees, max_features=sqrt) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10, "max_features": "sqrt"}, "min_tier": 3},
            },
            # ── Tier 4: heavy experiments (params halved vs original — feasible on strong workstations) ──
            {
                "task_name": "experiment_rf_massive",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20, all features) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_extreme",
                "task_description": f"5-fold CV GradientBoosting (500 trees, depth=8, lr=0.01) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 8, "learning_rate": 0.01}, "min_tier": 4},
            },
            {
                "task_name": "experiment_rf_mid_features_heavy",
                "task_description": f"5-fold CV RandomForest (400 trees, depth=15, {len(mid_features)} features) — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": mid_features, "cv_folds": 5, "params": {"n_estimators": 400, "max_depth": 15}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_fine_tuned",
                "task_description": f"5-fold CV GradientBoosting (400 trees, depth=8, lr=0.02) — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 400, "max_depth": 8, "learning_rate": 0.02}, "min_tier": 4},
            },
            {
                "task_name": "experiment_extra_trees_heavy",
                "task_description": f"5-fold CV ExtraTrees (500 trees, depth=20) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "extra_trees_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 4},
            },
        ]
    else:
        # Classification
        return [
            {
                "task_name": "experiment_logistic_baseline",
                "task_description": f"5-fold CV LogisticRegression on {dataset_name} (75K rows, all features)",
                "task_payload": {**base, "experiment_type": "logistic_regression", "features": all_features, "cv_folds": 5, "params": {"max_iter": 2000}, "min_tier": 2},
            },
            {
                "task_name": "experiment_logistic_l1",
                "task_description": f"5-fold CV LogisticRegression L1 (sparse feature selection)",
                "task_payload": {**base, "experiment_type": "logistic_regression_l1", "features": all_features, "cv_folds": 5, "params": {"max_iter": 2000, "C": 0.5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_decision_tree_deep",
                "task_description": f"5-fold CV DecisionTree (max_depth=15) on {display_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_classifier", "features": all_features, "cv_folds": 5, "params": {"max_depth": 15}, "min_tier": 2},
            },
            {
                "task_name": "experiment_random_forest_medium",
                "task_description": f"5-fold CV RandomForest (200 trees, depth=10) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 3},
            },
            {
                "task_name": "experiment_random_forest_heavy",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 3},
            },
            {
                "task_name": "experiment_gradient_boosting",
                "task_description": f"5-fold CV GradientBoosting (200 trees, depth=5, lr=0.1) on {display_name}",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1}, "min_tier": 3},
            },
            {
                "task_name": "experiment_feature_reduced",
                "task_description": f"5-fold CV RandomForest with reduced features ({', '.join(reduced_features)})",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": reduced_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 2},
            },
            {
                "task_name": "experiment_gb_tuned",
                "task_description": f"5-fold CV GradientBoosting tuned (500 trees, depth=8, lr=0.05)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 8, "learning_rate": 0.05}, "min_tier": 3},
            },
            # ── New model families ──
            {
                "task_name": "experiment_knn_classifier",
                "task_description": f"5-fold CV KNeighbors (k=5) on {display_name}",
                "task_payload": {**base, "experiment_type": "knn_classifier", "features": all_features, "cv_folds": 5, "params": {"n_neighbors": 5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_gaussian_nb",
                "task_description": f"5-fold CV GaussianNB on {display_name}",
                "task_payload": {**base, "experiment_type": "gaussian_nb", "features": all_features, "cv_folds": 5, "params": {}, "min_tier": 2},
            },
            {
                "task_name": "experiment_extra_trees",
                "task_description": f"5-fold CV ExtraTrees (300 trees, depth=15) on {display_name}",
                "task_payload": {**base, "experiment_type": "extra_trees_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 300, "max_depth": 15}, "min_tier": 3},
            },
            {
                "task_name": "experiment_adaboost",
                "task_description": f"5-fold CV AdaBoost (200 estimators, lr=0.1) on {display_name}",
                "task_payload": {**base, "experiment_type": "adaboost_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "learning_rate": 0.1}, "min_tier": 3},
            },
            {
                "task_name": "experiment_mlp",
                "task_description": f"5-fold CV MLPClassifier (100x50, max_iter=500) on {display_name}",
                "task_payload": {**base, "experiment_type": "mlp_classifier", "features": all_features, "cv_folds": 5, "params": {"hidden_layer_sizes": [100, 50], "max_iter": 500}, "min_tier": 3},
            },
            # ── Hyperparameter variants ──
            {
                "task_name": "experiment_decision_tree_shallow",
                "task_description": f"5-fold CV DecisionTree (max_depth=5) on {display_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_classifier", "features": all_features, "cv_folds": 5, "params": {"max_depth": 5}, "min_tier": 2},
            },
            {
                "task_name": "experiment_gb_stochastic",
                "task_description": f"5-fold CV GradientBoosting stochastic (subsample=0.8) on {display_name}",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 5, "learning_rate": 0.1, "subsample": 0.8}, "min_tier": 3},
            },
            {
                "task_name": "experiment_rf_sqrt_features",
                "task_description": f"5-fold CV RandomForest (200 trees, max_features=sqrt) on {display_name}",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10, "max_features": "sqrt"}, "min_tier": 3},
            },
            {
                "task_name": "experiment_logistic_high_c",
                "task_description": f"5-fold CV LogisticRegression (C=10.0) on {display_name}",
                "task_payload": {**base, "experiment_type": "logistic_regression", "features": all_features, "cv_folds": 5, "params": {"max_iter": 2000, "C": 10.0}, "min_tier": 2},
            },
            # ── Tier 4: heavy experiments (params halved — feasible on strong workstations) ──
            {
                "task_name": "experiment_rf_massive",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20, all features) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_extreme",
                "task_description": f"5-fold CV GradientBoosting (500 trees, depth=8, lr=0.01) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 8, "learning_rate": 0.01}, "min_tier": 4},
            },
            {
                "task_name": "experiment_rf_mid_features_heavy",
                "task_description": f"5-fold CV RandomForest (400 trees, depth=15, {len(mid_features)} features) — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": mid_features, "cv_folds": 5, "params": {"n_estimators": 400, "max_depth": 15}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_fine_tuned",
                "task_description": f"5-fold CV GradientBoosting (400 trees, depth=8, lr=0.02) — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 400, "max_depth": 8, "learning_rate": 0.02}, "min_tier": 4},
            },
            {
                "task_name": "experiment_extra_trees_heavy",
                "task_description": f"5-fold CV ExtraTrees (500 trees, depth=20) on {display_name} — Tier 4 (Tier 3 after queue wait)",
                "task_payload": {**base, "experiment_type": "extra_trees_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 4},
            },
        ]
