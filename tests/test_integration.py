"""
DCN Integration Test Suite

Tests planner decomposition, aggregator logic, auth lifecycle,
schema validation, and error handling — all without a live database.

Run:  cd backend && python -m pytest ../tests/test_integration.py -v
"""

import sys
import os
import json

# Add backend to path so imports work
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from planner import plan_tasks
from schemas import JobCreate, TaskClaim, TaskComplete, WorkerRegister, WorkerHeartbeat
from auth import verify_user, create_session, destroy_session, _sessions, load_users


# ═══════════════════════════════════════════════════════════════
# PLANNER TESTS
# ═══════════════════════════════════════════════════════════════

class TestPlannerDocumentAnalysis:
    """Document analysis planner should scale chunks with text size."""

    def test_empty_text_returns_single_task(self):
        tasks = plan_tasks("document_analysis", {"text": ""})
        assert len(tasks) == 1
        assert tasks[0]["task_name"] == "full_document_analysis"

    def test_short_text_returns_one_chunk(self):
        tasks = plan_tasks("document_analysis", {"text": "Short paragraph."})
        assert len(tasks) == 1
        assert "text_chunk" in tasks[0]["task_payload"]

    def test_medium_text_returns_multiple_chunks(self):
        paragraphs = "\n\n".join([f"Paragraph {i} with substantial content that explores the topic in detail and provides meaningful analysis. " * 3 for i in range(8)])
        tasks = plan_tasks("document_analysis", {"text": paragraphs})
        assert len(tasks) >= 2
        # Each task should have its own chunk
        for t in tasks:
            assert "text_chunk" in t["task_payload"]
            assert t["task_payload"]["chunk_index"] >= 1

    def test_large_text_caps_at_six_chunks(self):
        paragraphs = "\n\n".join([f"Long paragraph {i}. " * 20 for i in range(30)])
        tasks = plan_tasks("document_analysis", {"text": paragraphs})
        assert len(tasks) <= 6

    def test_chunk_indices_are_sequential(self):
        paragraphs = "\n\n".join([f"Paragraph {i} content here." for i in range(10)])
        tasks = plan_tasks("document_analysis", {"text": paragraphs})
        indices = [t["task_payload"]["chunk_index"] for t in tasks]
        assert indices == list(range(1, len(tasks) + 1))


class TestPlannerCodebaseReview:
    """Codebase review planner should create 3 focused review tasks."""

    def test_returns_three_review_focuses(self):
        tasks = plan_tasks("codebase_review", {"github_url": "https://github.com/user/repo"})
        assert len(tasks) == 3

    def test_review_names_are_distinct(self):
        tasks = plan_tasks("codebase_review", {"github_url": "https://github.com/user/repo"})
        names = [t["task_name"] for t in tasks]
        assert "core_logic_review" in names
        assert "architecture_review" in names
        assert "security_quality_review" in names

    def test_repo_label_extracted_from_url(self):
        tasks = plan_tasks("codebase_review", {"github_url": "https://github.com/fastapi/fastapi"})
        # The description should reference the repo name
        assert "fastapi/fastapi" in tasks[0]["task_description"]

    def test_missing_url_uses_fallback(self):
        tasks = plan_tasks("codebase_review", {})
        assert len(tasks) == 3
        assert "the codebase" in tasks[0]["task_description"]


class TestPlannerWebsiteBuilder:
    """Website builder planner should detect sections from user input."""

    def test_detects_explicit_sections(self):
        tasks = plan_tasks("website_builder", {
            "prompt": "Build a landing page with hero, features, pricing, and contact sections"
        })
        names = [t["task_name"] for t in tasks]
        assert any("hero" in n for n in names)
        assert any("pricing" in n for n in names)

    def test_falls_back_to_standard_sections(self):
        tasks = plan_tasks("website_builder", {"prompt": "Build me a website"})
        assert len(tasks) == 4  # hero_header, main_content, social_proof, cta_footer

    def test_each_section_has_order_metadata(self):
        tasks = plan_tasks("website_builder", {"prompt": "Build a website"})
        for t in tasks:
            assert "section_order" in t["task_payload"]
            assert "total_sections" in t["task_payload"]


class TestPlannerResearchPipeline:
    """Research pipeline planner should create 4 structured phases."""

    def test_returns_four_phases(self):
        tasks = plan_tasks("research_pipeline", {"topic": "quantum computing"})
        assert len(tasks) == 4

    def test_phases_have_distinct_names(self):
        tasks = plan_tasks("research_pipeline", {"topic": "AI safety"})
        names = [t["task_name"] for t in tasks]
        assert "phase_landscape_survey" in names
        assert "phase_deep_analysis" in names
        assert "phase_critical_evaluation" in names
        assert "phase_future_outlook" in names

    def test_topic_propagated_to_payload(self):
        tasks = plan_tasks("research_pipeline", {"topic": "distributed systems"})
        for t in tasks:
            assert t["task_payload"]["topic"] == "distributed systems"

    def test_fallback_topic_from_text(self):
        tasks = plan_tasks("research_pipeline", {"text": "machine learning optimization"})
        for t in tasks:
            assert "machine learning optimization" in t["task_payload"]["topic"]


class TestPlannerDataProcessing:
    """Data processing planner should split records into batches."""

    def test_empty_data_returns_single_task(self):
        tasks = plan_tasks("data_processing", {"data": ""})
        assert len(tasks) == 1

    def test_small_data_returns_one_batch(self):
        data = "\n".join([f"record_{i}" for i in range(3)])
        tasks = plan_tasks("data_processing", {"data": data})
        assert len(tasks) == 1
        assert tasks[0]["task_payload"]["batch_record_count"] == 3

    def test_medium_data_scales_batches(self):
        data = "\n".join([f"record_{i}" for i in range(30)])
        tasks = plan_tasks("data_processing", {"data": data})
        assert len(tasks) >= 2
        # Total records across batches should equal input
        total = sum(t["task_payload"]["batch_record_count"] for t in tasks)
        assert total == 30

    def test_large_data_caps_at_six_batches(self):
        data = "\n".join([f"record_{i}" for i in range(200)])
        tasks = plan_tasks("data_processing", {"data": data})
        assert len(tasks) <= 6


class TestPlannerMLExperiment:
    """ML experiment planner should generate tiered experiments."""

    def test_regression_returns_experiments(self):
        tasks = plan_tasks("ml_experiment", {"dataset_name": "weather_ri"})
        assert len(tasks) >= 8
        # Should have varied experiment types
        names = [t["task_name"] for t in tasks]
        assert "experiment_linear_baseline" in names
        assert "experiment_random_forest_heavy" in names

    def test_classification_returns_experiments(self):
        tasks = plan_tasks("ml_experiment", {"dataset_name": "customer_churn"})
        assert len(tasks) >= 8
        names = [t["task_name"] for t in tasks]
        assert "experiment_logistic_baseline" in names

    def test_experiments_have_ml_payload(self):
        tasks = plan_tasks("ml_experiment", {"dataset_name": "weather_ri"})
        for t in tasks:
            p = t["task_payload"]
            assert "dataset_name" in p
            assert "experiment_type" in p
            assert "features" in p
            assert "cv_folds" in p

    def test_tier_assignments_exist(self):
        tasks = plan_tasks("ml_experiment", {"dataset_name": "weather_ri"})
        tiers = [t["task_payload"].get("min_tier", 1) for t in tasks]
        assert any(t >= 3 for t in tiers), "Should have tier 3+ experiments"


class TestPlannerDistributedTypes:
    """Image, scraping, audio, sentiment planners should split input lists."""

    def test_image_processing_splits_urls(self):
        urls = [f"http://img.com/{i}.jpg" for i in range(9)]
        tasks = plan_tasks("image_processing", {"image_urls": urls})
        assert len(tasks) == 3
        total = sum(len(t["task_payload"]["image_urls"]) for t in tasks)
        assert total == 9

    def test_web_scraping_splits_urls(self):
        urls = [f"http://site.com/page{i}" for i in range(6)]
        tasks = plan_tasks("web_scraping", {"urls": urls})
        assert len(tasks) >= 2

    def test_sentiment_splits_text_list(self):
        texts = [f"I feel {s}" for s in ["great", "bad", "okay", "happy", "sad", "neutral"]]
        tasks = plan_tasks("sentiment_classification", {"texts": texts})
        assert len(tasks) >= 2

    def test_unknown_type_returns_generic(self):
        tasks = plan_tasks("unknown_task_type", {})
        assert len(tasks) == 3


# ═══════════════════════════════════════════════════════════════
# AUTH TESTS
# ═══════════════════════════════════════════════════════════════

class TestAuth:
    """Authentication and session management."""

    def test_load_users_returns_dict(self):
        users = load_users()
        assert isinstance(users, dict)
        assert "admin" in users
        assert "customer" in users

    def test_verify_valid_admin(self):
        user = verify_user("admin", "admin123")
        assert user is not None
        assert user["role"] == "admin"
        assert user["username"] == "admin"

    def test_verify_valid_customer(self):
        user = verify_user("customer", "customer123")
        assert user is not None
        assert user["role"] == "customer"

    def test_verify_bad_password(self):
        user = verify_user("admin", "wrongpassword")
        assert user is None

    def test_verify_nonexistent_user(self):
        user = verify_user("nobody", "anything")
        assert user is None

    def test_session_lifecycle(self):
        user = verify_user("admin", "admin123")
        token = create_session(user)
        assert token in _sessions
        assert _sessions[token]["username"] == "admin"

        destroy_session(token)
        assert token not in _sessions

    def test_destroy_nonexistent_session(self):
        # Should not raise
        destroy_session("fake_token_12345")


# ═══════════════════════════════════════════════════════════════
# SCHEMA VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestSchemas:
    """Pydantic schema validation."""

    def test_job_create_defaults(self):
        job = JobCreate(title="Test", task_type="document_analysis")
        assert job.priority == 1
        assert job.reward_amount == 0.0
        assert job.requires_validation is True
        assert job.input_payload == {}

    def test_job_create_with_payload(self):
        job = JobCreate(
            title="ML Test",
            task_type="ml_experiment",
            input_payload={"dataset_name": "weather_ri"},
            priority=5,
        )
        assert job.input_payload["dataset_name"] == "weather_ri"
        assert job.priority == 5

    def test_task_claim_defaults(self):
        claim = TaskClaim(worker_node_id="abc-123")
        assert claim.worker_tier == 1
        assert claim.task_types is None

    def test_task_claim_with_types(self):
        claim = TaskClaim(
            worker_node_id="abc-123",
            task_types=["ml_experiment", "document_analysis"],
            worker_tier=3,
        )
        assert len(claim.task_types) == 2
        assert claim.worker_tier == 3

    def test_task_complete_optional_fields(self):
        tc = TaskComplete()
        assert tc.result_text is None
        assert tc.result_payload is None
        assert tc.execution_time_seconds is None

    def test_task_complete_with_data(self):
        tc = TaskComplete(
            result_text="Done",
            result_payload={"accuracy": 0.95},
            execution_time_seconds=12.5,
        )
        assert tc.result_payload["accuracy"] == 0.95

    def test_worker_register(self):
        wr = WorkerRegister(node_name="gpu-node-1")
        assert wr.node_name == "gpu-node-1"
        assert wr.capabilities is None

    def test_worker_heartbeat(self):
        hb = WorkerHeartbeat(worker_node_id="abc-123")
        assert hb.worker_node_id == "abc-123"


# ═══════════════════════════════════════════════════════════════
# AGGREGATOR TESTS
# ═══════════════════════════════════════════════════════════════

class TestAggregator:
    """Aggregator concatenation and merge logic (no DB required)."""

    def test_concatenate_basic(self):
        from aggregator import concatenate_results
        results = [
            {"task_name": "chunk_1", "result_text": "First section content"},
            {"task_name": "chunk_2", "result_text": "Second section content"},
        ]
        output = concatenate_results(results, "document_analysis")
        assert "First section content" in output
        assert "Second section content" in output
        assert "chunk_1" in output

    def test_concatenate_website(self):
        from aggregator import concatenate_results
        results = [
            {"task_name": "section_hero", "result_text": "<div>Hero</div>"},
            {"task_name": "section_footer", "result_text": "<div>Footer</div>"},
        ]
        output = concatenate_results(results, "website_builder")
        assert "<div>Hero</div>" in output
        assert "<div>Footer</div>" in output

    def test_ml_aggregation_with_json(self):
        from aggregator import _aggregate_ml_experiment
        results = [
            {
                "task_order": 1,
                "task_name": "experiment_1",
                "result_text": '```json\n{"model_type": "linear_regression", "model_display": "LinearRegression", "r2": 0.85, "mse": 0.15, "mae": 0.10, "cv_r2_mean": 0.83, "cv_r2_std": 0.02, "dataset_name": "weather_ri", "target": "temperature", "task_category": "regression", "features": ["a", "b"], "params": {}, "n_total": 75000, "n_train": 60000, "n_test": 15000, "cv_folds": 5, "total_time_seconds": 2.5, "cv_time_seconds": 1.5, "train_time_seconds": 1.0, "primary_metric_name": "R2", "primary_metric_value": 0.85}\n```',
            },
            {
                "task_order": 2,
                "task_name": "experiment_2",
                "result_text": '```json\n{"model_type": "random_forest", "model_display": "RandomForest", "r2": 0.92, "mse": 0.08, "mae": 0.06, "cv_r2_mean": 0.90, "cv_r2_std": 0.01, "dataset_name": "weather_ri", "target": "temperature", "task_category": "regression", "features": ["a", "b", "c"], "params": {"n_estimators": 200}, "n_total": 75000, "n_train": 60000, "n_test": 15000, "cv_folds": 5, "total_time_seconds": 8.5, "cv_time_seconds": 5.5, "train_time_seconds": 3.0, "primary_metric_name": "R2", "primary_metric_value": 0.92}\n```',
            },
        ]
        job = {"title": "ML Test", "task_type": "ml_experiment"}
        output = _aggregate_ml_experiment(results, job)
        assert "RandomForest" in output
        assert "🏆" in output
        assert "0.92" in output
        assert "Model Comparison" in output

    def test_ml_aggregation_no_json_falls_back(self):
        from aggregator import _aggregate_ml_experiment, concatenate_results
        results = [
            {"task_order": 1, "task_name": "exp_1", "result_text": "No JSON here"},
        ]
        job = {"title": "ML Test", "task_type": "ml_experiment"}
        output = _aggregate_ml_experiment(results, job)
        # Falls back to concatenation
        assert "exp_1" in output

    def test_sentiment_merge(self):
        from aggregator import _merge_sentiment
        results = [
            {"result_text": "## Sentiment Classification Results\nAnalyzed 3 items\n### Summary\n- **Positive:** 2\n- **Negative:** 1\n- **Neutral:** 0\n### Detailed Results\n1. Happy - Positive\n2. Great - Positive\n3. Bad - Negative"},
            {"result_text": "## Sentiment Classification Results\nAnalyzed 3 items\n### Summary\n- **Positive:** 1\n- **Negative:** 0\n- **Neutral:** 2\n### Detailed Results\n4. Okay - Neutral\n5. Fine - Neutral\n6. Good - Positive"},
        ]
        output = _merge_sentiment(results, "## Sentiment\n\n", 6, 2)
        assert "Positive:** 3" in output
        assert "Negative:** 1" in output
        assert "Neutral:** 2" in output


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Edge cases and error paths."""

    def test_planner_with_none_payload(self):
        # Should not crash with empty/missing fields
        tasks = plan_tasks("document_analysis", {})
        assert len(tasks) >= 1

    def test_planner_with_missing_keys(self):
        tasks = plan_tasks("data_processing", {"unrelated_key": "value"})
        assert len(tasks) >= 1

    def test_planner_unknown_type(self):
        tasks = plan_tasks("nonexistent_type", {"text": "something"})
        assert len(tasks) == 3  # generic fallback

    def test_job_schema_rejects_missing_required(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            JobCreate()  # missing title and task_type

    def test_job_schema_rejects_missing_title(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            JobCreate(task_type="ml_experiment")  # missing title

    def test_claim_schema_rejects_missing_worker(self):
        import pytest
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            TaskClaim()  # missing worker_node_id


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
