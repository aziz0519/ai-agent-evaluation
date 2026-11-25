import json
from unittest.mock import patch

from evaluations.streamlit_ui import (
    configured_results_path,
    empty_metrics,
    load_dashboard_results,
    normalize_metric_name,
)


class _EmptySecrets:
    """A stand-in for st.secrets that always reports no configured values."""

    def get(self, key, default=None):
        return default


class TestNormalizeMetricName:
    def test_returns_original_name_for_unknown_metric(self):
        assert normalize_metric_name("Tool Correctness") == "Tool Correctness"
        assert normalize_metric_name("Plan Quality") == "Plan Quality"

    def test_strips_prefix_from_answer_correctness(self):
        assert normalize_metric_name("Answer Correctness") == "Answer Correctness"
        assert normalize_metric_name("Answer Correctness (extra)") == "Answer Correctness"
        assert normalize_metric_name("Answer Correctness Metric") == "Answer Correctness"

    def test_empty_string_returns_empty(self):
        assert normalize_metric_name("") == ""


class TestEmptyMetrics:
    def test_returns_metrics_with_none_score(self):
        metrics = empty_metrics()
        assert all(m["score"] is None for m in metrics.values())
        assert all(m["passed"] == 0 for m in metrics.values())


class TestConfiguredResultsPath:
    def test_returns_none_when_no_env_or_secrets(self, monkeypatch):
        monkeypatch.delenv("EVALUATION_RESULTS_PATH", raising=False)
        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            assert configured_results_path() is None

    def test_uses_env_var(self, monkeypatch):
        monkeypatch.setenv("EVALUATION_RESULTS_PATH", "/custom/path/report.json")
        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            path = configured_results_path()
            assert path.name == "report.json"
            assert path.parent.name == "path"
            assert path.parent.parent.name == "custom"

    def test_expands_user(self, monkeypatch):
        monkeypatch.setenv("EVALUATION_RESULTS_PATH", "~/custom/report.json")
        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            path = configured_results_path()
            assert path.is_absolute()
            assert "~" not in str(path)

    def test_resolves_relative_to_app_dir(self, monkeypatch):
        monkeypatch.setenv("EVALUATION_RESULTS_PATH", "relative/report.json")
        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            path = configured_results_path()
            assert path.is_absolute()
            assert path.name == "report.json"


class TestLoadDashboardResults:
    def test_loads_combined_report_from_default_path(self, tmp_path, monkeypatch):
        report_dir = tmp_path / "evaluations" / ".deepeval"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / ".latest_dashboard_results.json"
        report_data = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "test_case_count": 7,
            "metrics": [
                {"name": "Task Completion", "average_score": 0.9, "passed": 6, "failed": 1, "errors": 0, "threshold": 0.8},
            ],
        }
        report_file.write_text(json.dumps(report_data), encoding="utf-8")

        monkeypatch.setattr("evaluations.streamlit_ui.APP_DIR", tmp_path / "evaluations")
        monkeypatch.setattr("evaluations.streamlit_ui.DEFAULT_RESULTS_PATH", report_file)
        monkeypatch.setattr("evaluations.streamlit_ui.DEEPEVAL_RESULT_PATHS", (tmp_path / "irrelevant",))

        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            metrics, metadata, source, _warnings = load_dashboard_results()

        assert source == f"combined evaluation report ({report_file})"
        assert metadata["test_case_count"] == 7
        assert metrics["Task Completion"]["score"] == 0.9

    def test_falls_back_to_deepeval_run_when_no_combined(self, tmp_path, monkeypatch):
        report_dir = tmp_path / "evaluations" / ".deepeval"
        report_dir.mkdir(parents=True, exist_ok=True)
        report_file = report_dir / ".latest_run_full.json"
        report_data = {
            "testCases": [
                {"metricsData": [{"name": "Task Completion", "score": 0.85, "success": True}]}
            ]
        }
        report_file.write_text(json.dumps(report_data), encoding="utf-8")

        monkeypatch.setattr("evaluations.streamlit_ui.APP_DIR", tmp_path / "evaluations")
        monkeypatch.setattr("evaluations.streamlit_ui.DEFAULT_RESULTS_PATH", tmp_path / "evaluations" / ".deepeval" / ".latest_dashboard_results.json")
        monkeypatch.setattr("evaluations.streamlit_ui.DEEPEVAL_RESULT_PATHS", (report_file,))

        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            metrics, _metadata, source, _warnings = load_dashboard_results()

        assert "latest DeepEval run" in source
        assert metrics["Task Completion"]["score"] == 0.85

    def test_returns_empty_when_no_reports_found(self, tmp_path, monkeypatch):
        monkeypatch.setattr("evaluations.streamlit_ui.APP_DIR", tmp_path / "evaluations")
        monkeypatch.setattr("evaluations.streamlit_ui.DEFAULT_RESULTS_PATH", tmp_path / "evaluations" / ".deepeval" / ".latest_dashboard_results.json")
        monkeypatch.setattr("evaluations.streamlit_ui.DEEPEVAL_RESULT_PATHS", (tmp_path / "nonexistent.json",))

        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            metrics, metadata, source, _warnings = load_dashboard_results()

        assert source == "no evaluation results"
        assert metadata == {}
        for data in metrics.values():
            assert data["score"] is None

    def test_warns_when_configured_path_unreadable(self, tmp_path, monkeypatch):
        nonexistent_path = tmp_path / "nonexistent.json"
        monkeypatch.setenv("EVALUATION_RESULTS_PATH", str(nonexistent_path))
        monkeypatch.setattr("evaluations.streamlit_ui.APP_DIR", tmp_path / "evaluations")
        monkeypatch.setattr("evaluations.streamlit_ui.DEFAULT_RESULTS_PATH", tmp_path / "evaluations" / ".deepeval" / ".latest_dashboard_results.json")
        monkeypatch.setattr("evaluations.streamlit_ui.DEEPEVAL_RESULT_PATHS", (tmp_path / "irrelevant.json",))

        with patch("evaluations.streamlit_ui.st.secrets", _EmptySecrets()):
            _metrics, _metadata, _source, warnings = load_dashboard_results()

        assert any("EVALUATION_RESULTS_PATH is not readable" in w for w in warnings)