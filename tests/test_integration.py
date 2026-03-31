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


# ═══════════════════════════════════════════════════════════════
# PLANNER TESTS
# ═══════════════════════════════════════════════════════════════

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

    def test_unknown_type_returns_generic(self):
        tasks = plan_tasks("unknown_task_type", {})
        assert len(tasks) == 3


# ═══════════════════════════════════════════════════════════════
# SCHEMA VALIDATION TESTS
# ═══════════════════════════════════════════════════════════════

class TestSchemas:
    """Pydantic schema validation."""

    def test_job_create_defaults(self):
        job = JobCreate(title="Test", task_type="ml_experiment")
        assert job.priority == 1
        assert job.reward_amount == 0.0
        assert job.requires_validation is False
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
            task_types=["ml_experiment"],
            worker_tier=3,
        )
        assert len(claim.task_types) == 1
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
        from aggregator import _concatenate_results
        results = [
            {"task_name": "exp_1", "result_text": "First experiment"},
            {"task_name": "exp_2", "result_text": "Second experiment"},
        ]
        output = _concatenate_results(results)
        assert "First experiment" in output
        assert "Second experiment" in output
        assert "exp_1" in output

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
        assert "0.92" in output
        assert "Model Comparison" in output

    def test_ml_aggregation_no_json_falls_back(self):
        from aggregator import _aggregate_ml_experiment
        results = [
            {"task_order": 1, "task_name": "exp_1", "result_text": "No JSON here"},
        ]
        job = {"title": "ML Test", "task_type": "ml_experiment"}
        output = _aggregate_ml_experiment(results, job)
        # Falls back to concatenation
        assert "exp_1" in output


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════

class TestErrorHandling:
    """Edge cases and error paths."""

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
