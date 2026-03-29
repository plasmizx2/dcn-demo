"""
Planner module — splits a job into subtasks based on task_type.

Each task type has a dedicated planner that inspects the input payload
and dynamically determines the number of subtasks, their scope, and
the data each worker receives. Decomposition is deterministic and
adapts to input size, structure, and content.
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
# Each inspects the input payload and returns a list of subtask dicts
# with dynamically determined scope, count, and worker data.
# ──────────────────────────────────────────────


def _plan_document_analysis(input_payload: dict) -> list[dict]:
    """
    Inspect the document text and split into chunks based on paragraph
    structure and length. Short documents get fewer tasks; long documents
    get more (up to 6). Each subtask receives its own text chunk.
    """
    text = input_payload.get("text", "")

    if not text:
        # No text provided — single generic analysis task
        return [
            {"task_name": "full_document_analysis",
             "task_description": "Perform a comprehensive analysis of the document",
             "task_payload": {}}
        ]

    # Split on double newlines to find natural paragraph boundaries
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    total_chars = len(text)

    # Determine number of chunks based on document size
    if total_chars < 500 or len(paragraphs) <= 2:
        n_chunks = 1
    elif total_chars < 2000 or len(paragraphs) <= 5:
        n_chunks = 2
    elif total_chars < 5000 or len(paragraphs) <= 10:
        n_chunks = 3
    elif total_chars < 10000:
        n_chunks = 4
    else:
        n_chunks = min(6, max(3, len(paragraphs) // 3))

    # Distribute paragraphs evenly across chunks
    chunk_size = max(1, len(paragraphs) // n_chunks)
    chunks = []
    for i in range(n_chunks):
        start = i * chunk_size
        end = start + chunk_size if i < n_chunks - 1 else len(paragraphs)
        chunk_text = "\n\n".join(paragraphs[start:end])
        if chunk_text:
            chunks.append(chunk_text)

    if not chunks:
        chunks = [text]

    # Build subtasks with actual text chunks
    focus_areas = [
        "key themes, arguments, and main claims",
        "supporting evidence, data points, and examples",
        "implications, conclusions, and actionable insights",
        "methodology, structure, and logical coherence",
        "comparisons, contrasts, and contextual references",
        "gaps, limitations, and areas for further research",
    ]

    return [
        {
            "task_name": f"chunk_{i+1}_analysis",
            "task_description": (
                f"Analyze section {i+1}/{len(chunks)} of the document "
                f"({len(chunk.split())} words). Focus on: {focus_areas[i % len(focus_areas)]}"
            ),
            "task_payload": {
                "text_chunk": chunk,
                "chunk_index": i + 1,
                "total_chunks": len(chunks),
            },
        }
        for i, chunk in enumerate(chunks)
    ]


def _plan_codebase_review(input_payload: dict) -> list[dict]:
    """
    Create review tasks split by concern area. Each task focuses on a
    different aspect of code quality, making reviews more thorough
    than a single pass. The handler fetches actual repo files per task.
    """
    github_url = input_payload.get("github_url", "")
    repo_label = github_url.split("github.com/")[-1] if "github.com/" in github_url else "the codebase"

    # Define distinct review focus areas — each worker gets a different lens
    review_focuses = [
        {
            "task_name": "core_logic_review",
            "task_description": (
                f"Review the CORE SOURCE CODE of {repo_label}. Focus on: "
                f"main application logic, entry points, data flow, and algorithmic correctness. "
                f"Flag bugs, logic errors, and missing edge cases."
            ),
            "task_payload": {"review_focus": "core_logic", "file_priority": "source"},
        },
        {
            "task_name": "architecture_review",
            "task_description": (
                f"Review the ARCHITECTURE and CONFIGURATION of {repo_label}. Focus on: "
                f"project structure, dependency management, config files, build setup, and deployment. "
                f"Evaluate modularity, separation of concerns, and scalability patterns."
            ),
            "task_payload": {"review_focus": "architecture", "file_priority": "config"},
        },
        {
            "task_name": "security_quality_review",
            "task_description": (
                f"Review {repo_label} for SECURITY and CODE QUALITY. Focus on: "
                f"input validation, authentication, secrets handling, error handling, "
                f"type safety, naming conventions, and adherence to language best practices."
            ),
            "task_payload": {"review_focus": "security_quality", "file_priority": "source"},
        },
    ]

    return review_focuses


def _plan_website_builder(input_payload: dict) -> list[dict]:
    """
    Inspect the website description and decompose into logical page
    sections. Parses for explicit section requests or falls back to
    standard web page structure (hero, content, footer).
    """
    prompt_text = input_payload.get("prompt", "")

    # Try to detect explicit section requests from user input
    # e.g. "Build a landing page with hero, features, pricing, and contact sections"
    section_keywords = {
        "hero": "Hero/Banner Section — large heading, subtext, CTA button, background imagery",
        "header": "Header/Navigation — logo, nav links, responsive menu",
        "nav": "Header/Navigation — logo, nav links, responsive menu",
        "features": "Features Section — grid/cards showcasing key features with icons",
        "about": "About Section — company/product story, team info, mission statement",
        "pricing": "Pricing Section — tiered pricing cards with feature comparisons",
        "testimonials": "Testimonials Section — customer quotes, ratings, social proof",
        "contact": "Contact Section — contact form, email, phone, map embed",
        "footer": "Footer — links, social icons, copyright, newsletter signup",
        "gallery": "Gallery/Portfolio Section — image grid with lightbox",
        "faq": "FAQ Section — accordion-style questions and answers",
        "cta": "Call-to-Action Section — conversion-focused banner with button",
        "stats": "Statistics/Metrics Section — animated counters, key numbers",
        "team": "Team Section — member cards with photos and roles",
    }

    # Scan input for mentioned sections
    detected_sections = []
    prompt_lower = prompt_text.lower()
    for keyword, description in section_keywords.items():
        if keyword in prompt_lower:
            detected_sections.append((keyword, description))

    if len(detected_sections) >= 2:
        # User specified sections — build tasks from those
        tasks = []
        for i, (keyword, description) in enumerate(detected_sections):
            tasks.append({
                "task_name": f"section_{keyword}_build",
                "task_description": (
                    f"Build the {description} for the website. "
                    f"Website context: {prompt_text[:200]}"
                ),
                "task_payload": {
                    "section_type": keyword,
                    "section_description": description,
                    "section_order": i + 1,
                    "total_sections": len(detected_sections),
                },
            })
        return tasks

    # Fallback: standard page structure based on content length
    standard_sections = [
        ("hero_header", "Hero Section + Header — navigation bar, large hero banner with heading, "
         "subheadline, and primary CTA button. Set the visual tone for the entire site."),
        ("main_content", "Main Content Section — the core body of the page. Include features grid, "
         "about content, or product details based on the site purpose."),
        ("social_proof", "Social Proof + Credibility — testimonials, partner logos, statistics counters, "
         "or case study highlights that build trust."),
        ("cta_footer", "Call-to-Action + Footer — final conversion section with strong CTA, then footer "
         "with navigation links, social icons, and copyright."),
    ]

    return [
        {
            "task_name": f"section_{name}_build",
            "task_description": (
                f"Build the {desc} Website context: {prompt_text[:200]}"
            ),
            "task_payload": {
                "section_type": name,
                "section_description": desc,
                "section_order": i + 1,
                "total_sections": len(standard_sections),
            },
        }
        for i, (name, desc) in enumerate(standard_sections)
    ]


def _plan_research_pipeline(input_payload: dict) -> list[dict]:
    """
    Break research into structured phases. Each phase has a distinct
    research objective so workers explore different angles of the topic
    in parallel, producing a comprehensive final synthesis.
    """
    topic = input_payload.get("topic", "")

    if not topic:
        topic = input_payload.get("text", "general research topic")

    # Research phases — each worker tackles a different dimension
    phases = [
        {
            "task_name": "phase_landscape_survey",
            "task_description": (
                f"LANDSCAPE SURVEY for: {topic}. "
                f"Map the current state of the field — key players, technologies, "
                f"recent developments (last 2-3 years), and dominant approaches. "
                f"Provide a structured overview with categories and brief descriptions."
            ),
            "task_payload": {"research_phase": "landscape", "topic": topic},
        },
        {
            "task_name": "phase_deep_analysis",
            "task_description": (
                f"DEEP TECHNICAL ANALYSIS for: {topic}. "
                f"Dive into the technical details — how things work, trade-offs, "
                f"performance comparisons, architectural patterns, and implementation "
                f"considerations. Include specific data points and benchmarks where possible."
            ),
            "task_payload": {"research_phase": "technical", "topic": topic},
        },
        {
            "task_name": "phase_critical_evaluation",
            "task_description": (
                f"CRITICAL EVALUATION for: {topic}. "
                f"Assess strengths, weaknesses, gaps, and open problems. "
                f"Compare competing approaches. Identify what is overhyped vs. underappreciated. "
                f"What are the unsolved challenges and common failure modes?"
            ),
            "task_payload": {"research_phase": "critical", "topic": topic},
        },
        {
            "task_name": "phase_future_outlook",
            "task_description": (
                f"FUTURE OUTLOOK & RECOMMENDATIONS for: {topic}. "
                f"Predict where the field is heading, identify emerging trends, "
                f"and provide actionable recommendations. Who should adopt what, and when? "
                f"What are the risks of action vs. inaction?"
            ),
            "task_payload": {"research_phase": "outlook", "topic": topic},
        },
    ]

    return phases


def _plan_data_processing(input_payload: dict) -> list[dict]:
    """
    Split data into batches based on actual content size. Supports
    line-delimited data (CSV rows, JSON lines, log entries) and
    freeform text. Scales batch count with data volume.
    """
    data = input_payload.get("data", "")

    if not data:
        # No data provided — single generic processing task
        return [
            {"task_name": "full_data_processing",
             "task_description": "Process and classify the complete dataset",
             "task_payload": {}}
        ]

    # Split into records (lines)
    lines = [line.strip() for line in data.strip().split("\n") if line.strip()]
    total_lines = len(lines)

    # Determine batch count based on data volume
    if total_lines <= 5:
        n_batches = 1
    elif total_lines <= 20:
        n_batches = 2
    elif total_lines <= 50:
        n_batches = 3
    elif total_lines <= 100:
        n_batches = 4
    else:
        n_batches = min(6, max(3, total_lines // 25))

    # Distribute lines evenly
    batch_size = max(1, total_lines // n_batches)
    batches = []
    for i in range(n_batches):
        start = i * batch_size
        end = start + batch_size if i < n_batches - 1 else total_lines
        batch_lines = lines[start:end]
        if batch_lines:
            batches.append(batch_lines)

    if not batches:
        batches = [lines]

    # Determine processing focus per batch
    analysis_angles = [
        "classification, categorization, and labeling",
        "pattern detection, trends, and statistical summary",
        "anomaly detection, outliers, and data quality issues",
        "relationships, correlations, and cross-references",
        "aggregation, summary statistics, and key metrics",
        "structure validation and schema inference",
    ]

    return [
        {
            "task_name": f"batch_{i+1}_processing",
            "task_description": (
                f"Process data batch {i+1}/{len(batches)} ({len(batch)} records). "
                f"Focus on: {analysis_angles[i % len(analysis_angles)]}"
            ),
            "task_payload": {
                "data_batch": "\n".join(batch),
                "batch_index": i + 1,
                "total_batches": len(batches),
                "batch_record_count": len(batch),
            },
        }
        for i, batch in enumerate(batches)
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
            # ── Tier 4: datacenter-class heavy experiments ──
            {
                "task_name": "experiment_rf_massive",
                "task_description": f"10-fold CV RandomForest (1000 trees, depth=30, all features) on {dataset_name} — Tier 4 only",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 1000, "max_depth": 30}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_extreme",
                "task_description": f"10-fold CV GradientBoosting (1000 trees, depth=12, lr=0.01) on {dataset_name} — Tier 4 only",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 1000, "max_depth": 12, "learning_rate": 0.01}, "min_tier": 4},
            },
            {
                "task_name": "experiment_rf_mid_features_heavy",
                "task_description": f"10-fold CV RandomForest (800 trees, depth=25, {len(mid_features)} features) — Tier 4 only",
                "task_payload": {**base, "experiment_type": "random_forest_regressor", "features": mid_features, "cv_folds": 10, "params": {"n_estimators": 800, "max_depth": 25}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_fine_tuned",
                "task_description": f"10-fold CV GradientBoosting (800 trees, depth=10, lr=0.02) — Tier 4 only",
                "task_payload": {**base, "experiment_type": "gradient_boosting_regressor", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 800, "max_depth": 10, "learning_rate": 0.02}, "min_tier": 4},
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
            # ── Tier 4: datacenter-class heavy experiments ──
            {
                "task_name": "experiment_rf_massive",
                "task_description": f"10-fold CV RandomForest (1000 trees, depth=30, all features) on {dataset_name} — Tier 4 only",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 1000, "max_depth": 30}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_extreme",
                "task_description": f"10-fold CV GradientBoosting (1000 trees, depth=12, lr=0.01) on {dataset_name} — Tier 4 only",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 1000, "max_depth": 12, "learning_rate": 0.01}, "min_tier": 4},
            },
            {
                "task_name": "experiment_rf_mid_features_heavy",
                "task_description": f"10-fold CV RandomForest (800 trees, depth=25, {len(mid_features)} features) — Tier 4 only",
                "task_payload": {**base, "experiment_type": "random_forest_classifier", "features": mid_features, "cv_folds": 10, "params": {"n_estimators": 800, "max_depth": 25}, "min_tier": 4},
            },
            {
                "task_name": "experiment_gb_fine_tuned",
                "task_description": f"10-fold CV GradientBoosting (800 trees, depth=10, lr=0.02) — Tier 4 only",
                "task_payload": {**base, "experiment_type": "gradient_boosting_classifier", "features": all_features, "cv_folds": 10, "params": {"n_estimators": 800, "max_depth": 10, "learning_rate": 0.02}, "min_tier": 4},
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
