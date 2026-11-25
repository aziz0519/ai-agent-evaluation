"""Integration tests that require live API keys.

These tests are marked with @pytest.mark.integration and are deselected by default.
Run with: uv run pytest -m integration
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration


def _run_evaluation_script(script_name):
    if not os.environ.get("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set; skipping integration test")

    repo_root = Path(__file__).resolve().parents[1]
    subprocess.run(
        [sys.executable, str(repo_root / "evaluations" / script_name)],
        cwd=repo_root,
        check=True,
    )


class TestEvalPipelineIntegration:
    """Integration test for the full eval_all.py pipeline against real LLM."""

    def test_full_eval_pipeline_runs(self):
        """Run the complete evaluation pipeline against the real model.

        This test requires OPENAI_API_KEY to be set in the environment.
        It validates that the orchestration works end-to-end without crashing.
        """
        _run_evaluation_script("eval_all.py")

    def test_single_metric_script_runs(self):
        """Run a single metric evaluation script against the real model.

        Validates that the individual metric scripts (e.g., task_completion.py)
        can execute against the live model without errors.
        """
        _run_evaluation_script("task_completion.py")


class TestDashboardIntegration:
    """Integration test for the dashboard report generation and loading."""

    def test_dashboard_report_generated_and_loadable(self, monkeypatch):
        """Test that eval_all.py writes a report that streamlit_ui.py can load."""
        _run_evaluation_script("eval_all.py")

        from evaluations.eval_all import get_dashboard_report_path
        from evaluations.streamlit_ui import load_dashboard_results

        # Verify report exists
        report_path = get_dashboard_report_path()
        assert report_path.exists()

        # Verify the dashboard loads the report produced by this script.
        monkeypatch.setenv("EVALUATION_RESULTS_PATH", str(report_path))
        metrics, metadata, source, _warnings = load_dashboard_results()
        assert source == f"combined evaluation report ({report_path})"
        assert metadata.get("test_case_count") == 7
        assert len(metrics) == 7
