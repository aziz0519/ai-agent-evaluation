import json
import os
from pathlib import Path

import streamlit as st


METRIC_THRESHOLDS = {
    "Task Completion": 0.8,
    "Step Efficiency": 0.8,
    "Plan Quality": 0.8,
    "Plan Adherence": 0.8,
    "Tool Correctness": 0.9,
    "Argument Correctness": 0.8,
    "Answer Correctness": 0.8,
}

DEFAULT_RESULTS_PATH = (
    Path(__file__).resolve().parent / ".deepeval" / ".latest_dashboard_results.json"
)
DEEPEVAL_RESULTS_PATH = (
    Path(__file__).resolve().parent / ".deepeval" / ".latest_run_full.json"
)
DEEPEVAL_RESULT_PATHS = (
    Path.cwd() / ".deepeval" / ".latest_run_full.json",
    DEEPEVAL_RESULTS_PATH,
)


def normalize_metric_name(name):
    if not isinstance(name, str):
        return None
    if name.startswith("Answer Correctness"):
        return "Answer Correctness"
    return name


def empty_metrics():
    return {
        name: {
            "score": None,
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "threshold": threshold,
        }
        for name, threshold in METRIC_THRESHOLDS.items()
    }


def configured_results_path():
    """Return the configured report path, if one was provided."""
    path_value = os.environ.get("EVALUATION_RESULTS_PATH")
    if not path_value:
        # Local runs can keep the path in .streamlit/secrets.toml.
        try:
            path_value = st.secrets.get("deepeval", {}).get("results_path")
        except FileNotFoundError:
            path_value = None

    if not path_value:
        return None

    results_path = Path(path_value).expanduser()
    if not results_path.is_absolute():
        results_path = Path.cwd() / results_path
    return results_path


def read_json_object(path):
    """Read a JSON object, returning None when the file is not readable.

    Deployment filesystems such as Unity Catalog volume FUSE mounts do not
    always report file existence reliably, so read the file directly instead
    of checking Path.exists() or Path.is_file() first.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"Expected a JSON object in {path}")
    return data


def as_number(value, default=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return default
    return float(value)


def as_count(value, default=0):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return default
    return value


def metrics_from_report(data):
    metrics = empty_metrics()
    for result in data.get("metrics", []):
        if not isinstance(result, dict):
            continue
        name = normalize_metric_name(result.get("name"))
        if name not in metrics:
            continue
        metrics[name] = {
            "score": as_number(result.get("average_score")),
            "passed": as_count(result.get("passed")),
            "failed": as_count(result.get("failed")),
            "errors": as_count(result.get("errors")),
            "threshold": as_number(
                result.get("threshold"), METRIC_THRESHOLDS[name]
            ),
        }
    return metrics


def metrics_from_deepeval_report(data):
    metrics = empty_metrics()
    scores = {name: [] for name in METRIC_THRESHOLDS}

    for test_case in data.get("testCases", []):
        if not isinstance(test_case, dict):
            continue
        for result in test_case.get("metricsData", []):
            if not isinstance(result, dict):
                continue
            name = normalize_metric_name(result.get("name"))
            if name not in metrics:
                continue

            score = as_number(result.get("score"))
            if score is None:
                metrics[name]["failed"] += 1
                metrics[name]["errors"] += 1
                continue

            scores[name].append(score)
            success = result.get("success")
            if not isinstance(success, bool):
                success = score >= metrics[name]["threshold"]
            metrics[name]["passed" if success else "failed"] += 1

    for name, metric_scores in scores.items():
        if metric_scores:
            metrics[name]["score"] = sum(metric_scores) / len(metric_scores)
    return metrics


def load_dashboard_results():
    warnings = []
    configured_path = configured_results_path()

    # Prefer a combined dashboard report. The configured path is tried
    # first, then local defaults. A bad configured path is reported as a
    # warning instead of preventing the app from starting.
    combined_paths = [
        DEFAULT_RESULTS_PATH,
        Path.cwd() / ".deepeval" / ".latest_dashboard_results.json",
    ]
    if configured_path is not None:
        combined_paths.insert(0, configured_path)

    unreadable_paths = set()
    for results_path in combined_paths:
        if results_path in unreadable_paths:
            continue

        data = read_json_object(results_path)
        if data is None:
            unreadable_paths.add(results_path)
            if results_path == configured_path:
                warnings.append(
                    "EVALUATION_RESULTS_PATH is not readable: "
                    f"{results_path}. Using a local fallback instead."
                )
            continue

        if isinstance(data.get("metrics"), list):
            return (
                metrics_from_report(data),
                data,
                f"combined evaluation report ({results_path})",
                warnings,
            )

    # Fall back to the latest raw DeepEval run when no combined report is
    # available. This can provide partial metric coverage.
    deepeval_paths = list(DEEPEVAL_RESULT_PATHS)
    if configured_path is not None:
        deepeval_paths.insert(0, configured_path)

    for results_path in deepeval_paths:
        if results_path in unreadable_paths:
            continue

        data = read_json_object(results_path)
        if data is None:
            continue

        if isinstance(data.get("testCases"), list):
            return (
                metrics_from_deepeval_report(data),
                data,
                f"latest DeepEval run ({results_path})",
                warnings,
            )

    return empty_metrics(), {}, "no evaluation results", warnings


def main():
    st.set_page_config(page_title="Agent Evaluation Dashboard", layout="wide")
    st.title("Agent Evaluation Dashboard")
    st.caption("Scores and passing rates for the seven agent evaluation metrics.")

    try:
        metrics, metadata, source, warnings = load_dashboard_results()
    except (
        OSError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as error:
        st.error(f"Could not read evaluation results: {error}")
        st.stop()

    for warning in warnings:
        st.warning(warning)

    st.caption(f"Data source: {source}")
    if source == "no evaluation results":
        st.warning(
            "No evaluation report was found. The `.deepeval` directory is "
            "git-ignored, so it is not included in normal deployments. Set "
            "`EVALUATION_RESULTS_PATH` or the `deepeval.results_path` value "
            "in `.streamlit/secrets.toml` to the combined report file's path."
        )
    if isinstance(metadata, dict):
        if metadata.get("generated_at"):
            st.caption(f"Latest combined run: {metadata['generated_at']}")
        if metadata.get("test_case_count") is not None:
            st.caption(f"Test cases: {metadata['test_case_count']}")

    columns = st.columns(4)
    for index, (name, result) in enumerate(metrics.items()):
        score = result["score"]
        score_label = f"{score:.1%}" if score is not None else "N/A"
        with columns[index % len(columns)]:
            st.metric(
                label=name,
                value=score_label,
                help=(
                    f"Average score across evaluated cases. Passing threshold: "
                    f"{result['threshold']:.0%}."
                ),
            )
            if result["errors"]:
                st.caption(f"Evaluation errors: {result['errors']}")
            elif result["score"] is None:
                st.caption("No recorded result yet.")

    st.subheader("Passing rate by metric")
    chart_data = {
        "Metric": list(metrics),
        "Passed": [result["passed"] for result in metrics.values()],
        "Failed": [result["failed"] for result in metrics.values()],
    }
    st.bar_chart(
        chart_data,
        x="Metric",
        y=["Passed", "Failed"],
        color=["#2e8b57", "#d9534f"],
    )
    st.caption("Bars show the number of passing and failing test cases for each metric.")


if __name__ == "__main__":
    main()
