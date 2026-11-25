"""Unit tests for the evaluation pipeline helpers in evaluations/eval_all.py."""

import json
from datetime import datetime
from unittest.mock import MagicMock

# Import the helpers we extracted from eval_all.py
from evaluations.eval_all import (
    build_metric_results_payload,
    extract_tools_called,
    get_dashboard_report_path,
    normalize_metric_name,
    write_dashboard_results,
)


class TestNormalizeMetricName:
    """Tests for the metric name normalization helper."""

    def test_returns_original_name_for_unknown_metric(self):
        assert normalize_metric_name("Tool Correctness") == "Tool Correctness"
        assert normalize_metric_name("Plan Quality") == "Plan Quality"

    def test_strips_prefix_from_answer_correctness(self):
        assert normalize_metric_name("Answer Correctness") == "Answer Correctness"
        assert normalize_metric_name("Answer Correctness (extra)") == "Answer Correctness"
        assert normalize_metric_name("Answer Correctness Metric") == "Answer Correctness"

    def test_empty_string_returns_empty(self):
        assert normalize_metric_name("") == ""


class TestExtractToolsCalled:
    """Tests for extracting tool calls from agent response messages."""

    def test_extracts_single_tool_call(self):
        msg = MagicMock()
        msg.tool_calls = [{"name": "get_user_purchase_history", "args": {"user": "user123"}}]
        tools = extract_tools_called([msg])
        assert len(tools) == 1
        assert tools[0].name == "get_user_purchase_history"
        assert tools[0].input_parameters == {"user": "user123"}

    def test_extracts_multiple_tool_calls_from_one_message(self):
        msg = MagicMock()
        msg.tool_calls = [
            {"name": "get_user_purchase_history", "args": {"user": "user123"}},
            {"name": "get_today_date", "args": {}},
        ]
        tools = extract_tools_called([msg])
        assert len(tools) == 2
        assert [t.name for t in tools] == ["get_user_purchase_history", "get_today_date"]

    def test_extracts_tool_calls_from_multiple_messages(self):
        msg1 = MagicMock()
        msg1.tool_calls = [{"name": "get_user_purchase_history", "args": {"user": "user123"}}]
        msg2 = MagicMock()
        msg2.tool_calls = [{"name": "calculate_right_refund", "args": {"user": "user123", "items": [{"name": "book"}]}}]
        tools = extract_tools_called([msg1, msg2])
        assert len(tools) == 2

    def test_handles_message_without_tool_calls_attribute(self):
        msg = MagicMock(spec=[])
        tools = extract_tools_called([msg])
        assert tools == []

    def test_handles_message_with_none_tool_calls(self):
        msg = MagicMock()
        msg.tool_calls = None
        tools = extract_tools_called([msg])
        assert tools == []

    def test_handles_empty_list(self):
        assert extract_tools_called([]) == []


class TestBuildMetricResultsPayload:
    """Tests for building the dashboard metrics payload from evaluation results."""

    def _make_metric_data(self, name, score, success=None):
        md = MagicMock()
        md.name = name
        md.score = score
        md.success = success
        return md

    def _make_test_result(self, metrics_data):
        tr = MagicMock()
        tr.metrics_data = metrics_data
        return tr

    def _make_evaluation_result(self, test_results):
        er = MagicMock()
        er.test_results = test_results
        return er

    def test_basic_aggregation_single_metric(self):
        metric_data = self._make_metric_data("Task Completion", 0.9, True)
        test_result = self._make_test_result([metric_data])
        trace_result = self._make_evaluation_result([test_result])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 1)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert metrics["Task Completion"]["average_score"] == 0.9
        assert metrics["Task Completion"]["passed"] == 1
        assert metrics["Task Completion"]["failed"] == 0
        assert metrics["Task Completion"]["errors"] == 0
        assert metrics["Task Completion"]["threshold"] == 0.8

    def test_score_none_counted_as_failed_and_error(self):
        metric_data = self._make_metric_data("Task Completion", None)
        test_result = self._make_test_result([metric_data])
        trace_result = self._make_evaluation_result([test_result])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 1)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert metrics["Task Completion"]["average_score"] is None
        assert metrics["Task Completion"]["passed"] == 0
        assert metrics["Task Completion"]["failed"] == 1
        assert metrics["Task Completion"]["errors"] == 1

    def test_success_none_derived_from_threshold(self):
        metric_data = self._make_metric_data("Task Completion", 0.7, None)  # below 0.8 threshold
        test_result = self._make_test_result([metric_data])
        trace_result = self._make_evaluation_result([test_result])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 1)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert metrics["Task Completion"]["passed"] == 0
        assert metrics["Task Completion"]["failed"] == 1

    def test_averages_multiple_scores(self):
        md1 = self._make_metric_data("Task Completion", 0.8, True)
        md2 = self._make_metric_data("Task Completion", 1.0, True)
        test_result = self._make_test_result([md1, md2])
        trace_result = self._make_evaluation_result([test_result])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 2)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert metrics["Task Completion"]["average_score"] == 0.9
        assert metrics["Task Completion"]["passed"] == 2

    def test_combines_trace_and_single_turn_results(self):
        md_trace = self._make_metric_data("Task Completion", 0.8, True)
        md_single = self._make_metric_data("Tool Correctness", 0.9, True)
        trace_result = self._make_evaluation_result([self._make_test_result([md_trace])])
        single_turn_result = self._make_evaluation_result([self._make_test_result([md_single])])

        payload = build_metric_results_payload(trace_result, single_turn_result, 1)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert metrics["Task Completion"]["passed"] == 1
        assert metrics["Tool Correctness"]["passed"] == 1

    def test_includes_generated_at_and_test_case_count(self):
        trace_result = self._make_evaluation_result([])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 7)

        assert payload["test_case_count"] == 7
        assert "generated_at" in payload
        # Validate ISO format
        datetime.fromisoformat(payload["generated_at"])

    def test_unknown_metric_names_are_ignored(self):
        metric_data = self._make_metric_data("Unknown Metric", 0.5)
        test_result = self._make_test_result([metric_data])
        trace_result = self._make_evaluation_result([test_result])
        single_turn_result = self._make_evaluation_result([])

        payload = build_metric_results_payload(trace_result, single_turn_result, 1)

        metrics = {m["name"]: m for m in payload["metrics"]}
        assert "Unknown Metric" not in metrics


class TestGetDashboardReportPath:
    """Tests for the report path resolver."""

    def test_returns_path_in_evaluations_deepeval(self):
        path = get_dashboard_report_path()
        assert path.name == ".latest_dashboard_results.json"
        assert path.parent.name == ".deepeval"
        assert path.parent.parent.name == "evaluations"


class TestWriteDashboardResults:
    """Integration test for the full write path."""

    def test_writes_valid_json_to_temp_path(self, tmp_path, monkeypatch):
        # Monkeypatch the path to use our temp directory
        fake_path = tmp_path / ".deepeval" / ".latest_dashboard_results.json"
        monkeypatch.setattr(
            "evaluations.eval_all.get_dashboard_report_path",
            lambda: fake_path,
        )

        trace_result = MagicMock()
        trace_result.test_results = []
        single_turn_result = MagicMock()
        single_turn_result.test_results = []

        write_dashboard_results(trace_result, single_turn_result, 3)

        assert fake_path.exists()
        data = json.loads(fake_path.read_text(encoding="utf-8"))
        assert data["test_case_count"] == 3
        assert "metrics" in data
        assert len(data["metrics"]) == 7  # all 7 metrics present