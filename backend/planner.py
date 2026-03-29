"""
Planner module — splits a job into subtasks based on task_type.

Each task type has its own section so you can plug in real splitting
logic later (e.g. measure document size, scan codebase modules, etc.).
For now, each type returns 3 placeholder subtasks.
"""


def plan_tasks(task_type: str, input_payload: dict) -> list[dict]:
    """
    Given a task_type and the job's input_payload, return a list of subtask dicts.
    Each dict has: task_name, task_description, task_payload

    To add real logic later, edit the section for that task_type.
    """

    if task_type == "document_analysis":
        return _plan_document_analysis(input_payload)

    elif task_type == "codebase_review":
        return _plan_codebase_review(input_payload)

    elif task_type == "website_builder":
        return _plan_website_builder(input_payload)

    elif task_type == "research_pipeline":
        return _plan_research_pipeline(input_payload)

    elif task_type == "data_processing":
        return _plan_data_processing(input_payload)

    elif task_type == "ml_experiment":
        return _plan_ml_experiment(input_payload)

    elif task_type == "image_processing":
        return _plan_image_processing(input_payload)

    elif task_type == "web_scraping":
        return _plan_web_scraping(input_payload)

    elif task_type == "audio_transcription":
        return _plan_audio_transcription(input_payload)

    elif task_type == "sentiment_classification":
        return _plan_sentiment_classification(input_payload)

    else:
        # Unknown task type — create 3 generic subtasks
        return [
            {"task_name": f"step_{i}", "task_description": f"Subtask {i} for {task_type}", "task_payload": {}}
            for i in range(1, 4)
        ]


# ──────────────────────────────────────────────
# Task-type-specific planners
# Each returns a list of subtask dicts.
# Replace placeholder logic with real splitting later.
# ──────────────────────────────────────────────


def _plan_document_analysis(input_payload: dict) -> list[dict]:
    """
    TODO: Later, inspect input_payload for document size and split
    into chunks accordingly. For now, always splits into 3 chunks.
    """
    return [
        {"task_name": "chunk_1_analysis", "task_description": "Analyze chunk 1 of the document (scope TBD by worker)", "task_payload": {}},
        {"task_name": "chunk_2_analysis", "task_description": "Analyze chunk 2 of the document (scope TBD by worker)", "task_payload": {}},
        {"task_name": "chunk_3_analysis", "task_description": "Analyze chunk 3 of the document (scope TBD by worker)", "task_payload": {}},
    ]


def _plan_codebase_review(input_payload: dict) -> list[dict]:
    """
    TODO: Later, scan the actual codebase and split by real modules/directories.
    For now, creates 3 generic sections.
    """
    return [
        {"task_name": "section_1_review", "task_description": "Review section 1 of the codebase (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_2_review", "task_description": "Review section 2 of the codebase (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_3_review", "task_description": "Review section 3 of the codebase (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_website_builder(input_payload: dict) -> list[dict]:
    """
    TODO: Later, inspect input_payload for requested page sections.
    For now, creates 3 generic sections.
    """
    return [
        {"task_name": "section_1_build", "task_description": "Build section 1 of the website (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_2_build", "task_description": "Build section 2 of the website (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "section_3_build", "task_description": "Build section 3 of the website (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_research_pipeline(input_payload: dict) -> list[dict]:
    """
    TODO: Later, break research into phases based on input_payload topic.
    For now, creates 3 generic phases.
    """
    return [
        {"task_name": "phase_1_research", "task_description": "Research phase 1 (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "phase_2_research", "task_description": "Research phase 2 (specific scope TBD by worker)", "task_payload": {}},
        {"task_name": "phase_3_research", "task_description": "Research phase 3 (specific scope TBD by worker)", "task_payload": {}},
    ]


def _plan_data_processing(input_payload: dict) -> list[dict]:
    """
    TODO: Later, split by actual data size or batch count.
    For now, always creates 3 batches.
    """
    return [
        {"task_name": "batch_1_processing", "task_description": "Process batch 1 of the data (scope TBD by worker)", "task_payload": {}},
        {"task_name": "batch_2_processing", "task_description": "Process batch 2 of the data (scope TBD by worker)", "task_payload": {}},
        {"task_name": "batch_3_processing", "task_description": "Process batch 3 of the data (scope TBD by worker)", "task_payload": {}},
    ]


def _plan_ml_experiment(input_payload: dict) -> list[dict]:
    """
    Generate 8 heavy ML experiment subtasks — each trains a different model/config
    with cross-validation on 75K rows. Actually makes the CPU sweat.
    """
    from datasets import DATASETS

    dataset_name = input_payload.get("dataset_name", "weather_ri")
    ds_info = DATASETS.get(dataset_name, DATASETS["weather_ri"])

    target = ds_info["target"]
    task_category = ds_info["task_category"]
    all_features = ds_info["all_features"]
    reduced_features = all_features[:5]  # first 5 features for reduced experiments
    mid_features = all_features[:len(all_features) // 2]  # half the features

    base = {
        "dataset_name": dataset_name,
        "target": target,
        "task_category": task_category,
    }

    if task_category == "regression":
        return [
            {
                "task_name": "experiment_linear_baseline",
                "task_description": f"5-fold CV LinearRegression on {dataset_name} (75K rows, all features)",
                "task_payload": {**base, "experiment_type": "linear_regression", "features": all_features, "cv_folds": 5, "params": {}, "min_tier": 2},
            },
            {
                "task_name": "experiment_ridge_regression",
                "task_description": f"5-fold CV Ridge (alpha=1.0) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "ridge_regression", "features": all_features, "cv_folds": 5, "params": {"alpha": 1.0}, "min_tier": 2},
            },
            {
                "task_name": "experiment_decision_tree_deep",
                "task_description": f"5-fold CV DecisionTree (max_depth=15) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_regressor", "features": all_features, "cv_folds": 5, "params": {"max_depth": 15}, "min_tier": 2},
            },
            {
                "task_name": "experiment_random_forest_medium",
                "task_description": f"5-fold CV RandomForest (200 trees, depth=10) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 3},
            },
            {
                "task_name": "experiment_random_forest_heavy",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 3},
            },
            {
                "task_name": "experiment_gradient_boosting",
                "task_description": f"5-fold CV GradientBoosting (200 trees, depth=5, lr=0.1) on {dataset_name}",
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
                "task_description": f"5-fold CV DecisionTree (max_depth=15) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "decision_tree_classifier", "features": all_features, "cv_folds": 5, "params": {"max_depth": 15}, "min_tier": 2},
            },
            {
                "task_name": "experiment_random_forest_medium",
                "task_description": f"5-fold CV RandomForest (200 trees, depth=10) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 200, "max_depth": 10}, "min_tier": 3},
            },
            {
                "task_name": "experiment_random_forest_heavy",
                "task_description": f"5-fold CV RandomForest (500 trees, depth=20) on {dataset_name}",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 5, "params": {"n_estimators": 500, "max_depth": 20}, "min_tier": 3},
            },
            {
                "task_name": "experiment_gradient_boosting",
                "task_description": f"5-fold CV GradientBoosting (200 trees, depth=5, lr=0.1) on {dataset_name}",
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
        ]


# ──────────────────────────────────────────────
# Distributed worker task types (no AI API needed)
# ──────────────────────────────────────────────


def _plan_image_processing(input_payload: dict) -> list[dict]:
    """Split image batch across workers."""
    urls = input_payload.get("image_urls", [])
    if not urls:
        return [
            {"task_name": f"image_batch_{i}", "task_description": f"Process image batch {i}", "task_payload": {}}
            for i in range(1, 4)
        ]
    # Split URLs into 3 batches
    batch_size = max(1, len(urls) // 3)
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    return [
        {"task_name": f"image_batch_{i+1}", "task_description": f"Resize/compress {len(b)} images", "task_payload": {"image_urls": b}}
        for i, b in enumerate(batches[:3])
    ]


def _plan_web_scraping(input_payload: dict) -> list[dict]:
    """Split URLs across workers."""
    urls = input_payload.get("urls", [])
    if not urls:
        return [
            {"task_name": f"scrape_batch_{i}", "task_description": f"Scrape URL batch {i}", "task_payload": {}}
            for i in range(1, 4)
        ]
    batch_size = max(1, len(urls) // 3)
    batches = [urls[i:i + batch_size] for i in range(0, len(urls), batch_size)]
    return [
        {"task_name": f"scrape_batch_{i+1}", "task_description": f"Scrape {len(b)} URLs and extract data", "task_payload": {"urls": b}}
        for i, b in enumerate(batches[:3])
    ]


def _plan_audio_transcription(input_payload: dict) -> list[dict]:
    """Split audio files across workers."""
    files = input_payload.get("audio_urls", [])
    if not files:
        return [
            {"task_name": f"transcribe_batch_{i}", "task_description": f"Transcribe audio batch {i}", "task_payload": {}}
            for i in range(1, 4)
        ]
    batch_size = max(1, len(files) // 3)
    batches = [files[i:i + batch_size] for i in range(0, len(files), batch_size)]
    return [
        {"task_name": f"transcribe_batch_{i+1}", "task_description": f"Transcribe {len(b)} audio files", "task_payload": {"audio_urls": b}}
        for i, b in enumerate(batches[:3])
    ]


def _plan_sentiment_classification(input_payload: dict) -> list[dict]:
    """Split text items across workers for sentiment analysis."""
    items = input_payload.get("texts", [])
    if not items:
        text = input_payload.get("text", "")
        if text:
            # Split long text into paragraphs/sentences
            paragraphs = [p.strip() for p in text.split("\n") if p.strip()]
            if len(paragraphs) < 3:
                paragraphs = [text]
            batch_size = max(1, len(paragraphs) // 3)
            batches = [paragraphs[i:i + batch_size] for i in range(0, len(paragraphs), batch_size)]
            return [
                {"task_name": f"sentiment_batch_{i+1}", "task_description": f"Classify sentiment of {len(b)} items", "task_payload": {"texts": b}}
                for i, b in enumerate(batches[:3])
            ]
        return [
            {"task_name": f"sentiment_batch_{i}", "task_description": f"Classify sentiment batch {i}", "task_payload": {}}
            for i in range(1, 4)
        ]
    batch_size = max(1, len(items) // 3)
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
    return [
        {"task_name": f"sentiment_batch_{i+1}", "task_description": f"Classify {len(b)} items", "task_payload": {"texts": b}}
        for i, b in enumerate(batches[:3])
    ]
