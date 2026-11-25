"""Integration tests that require live API keys.

These tests are marked with @pytest.mark.integration and are skipped by default.
Run with: uv run pytest -m integration
"""

import pytest

# Mark all tests in this module as integration
pytestmark = pytest.mark.integration


class TestEvalPipelineIntegration:
    """Integration test for the full eval_all.py pipeline against real LLM."""

    def test_full_eval_pipeline_runs(self):
        """Run the complete evaluation pipeline against the real model.

        This test requires OPENAI_API_KEY to be set in the environment.
        It validates that the orchestration works end-to-end without crashing.
        """
        import os

        # Skip if no API key is available
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set; skipping integration test")

        from evaluations.eval_all import main

        # This should run without raising exceptions
        main()

    def test_single_metric_script_runs(self):
        """Run a single metric evaluation script against the real model.

        Validates that the individual metric scripts (e.g., task_completion.py)
        can execute against the live model without errors.
        """
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set; skipping integration test")

        # We just test that the script can be imported and run without error
        # The script executes at import time (no main guard), so we just import
        from evaluations import task_completion  # noqa: F401

        # If we reach here, the script ran without crashing
        assert True


class TestDashboardIntegration:
    """Integration test for the dashboard report generation and loading."""

    def test_dashboard_report_generated_and_loadable(self, tmp_path, monkeypatch):
        """Test that eval_all.py writes a report that streamlit_ui.py can load."""
        import os

        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set; skipping integration test")

        from evaluations.eval_all import get_dashboard_report_path, main
        from evaluations.streamlit_ui import load_dashboard_results

        # Run the evaluation
        main()

        # Verify report exists
        report_path = get_dashboard_report_path()
        assert report_path.exists()

        # Verify dashboard can load it
        metrics, metadata, source, _warnings = load_dashboard_results()
        assert source != "no evaluation results"
        assert metadata.get("test_case_count") == 7
        assert len(metrics) == 7