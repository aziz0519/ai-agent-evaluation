import json
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

RESULTS_PATH = Path(__file__).resolve().parent / ".deepeval" / ".latest_dashboard_results.json"
DEEPEVAL_RESULTS_PATH = Path(__file__).resolve().parent / ".deepeval" / ".latest_run_full.json"
DEEPEVAL_RESULT_PATHS = (
    Path.cwd() / ".deepeval" / ".latest_run_full.json",
    DEEPEVAL_RESULTS_PATH,
)


def normalize_metric_name(name):
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


def load_dashboard_results():
    if RESULTS_PATH.exists():
        data = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        metrics = empty_metrics()
        for result in data.get("metrics", []):
            name = normalize_metric_name(result["name"])
            if name not in metrics:
                continue
            metrics[name] = {
                "score": result.get("average_score"),
                "passed": result.get("passed", 0),
                "failed": result.get("failed", 0),
                "errors": result.get("errors", 0),
                "threshold": result.get("threshold", METRIC_THRESHOLDS[name]),
            }
        return metrics, data, "combined evaluation report"

    deepeval_results_path = next(
        (path for path in DEEPEVAL_RESULT_PATHS if path.exists()),
        None,
    )
    if deepeval_results_path is not None:
        data = json.loads(deepeval_results_path.read_text(encoding="utf-8"))
        metrics = empty_metrics()
        scores = {name: [] for name in METRIC_THRESHOLDS}

        for test_case in data.get("testCases", []):
            for result in test_case.get("metricsData", []):
                name = normalize_metric_name(result.get("name", ""))
                if name not in metrics:
                    continue

                score = result.get("score")
                if not isinstance(score, (int, float)):
                    metrics[name]["failed"] += 1
                    metrics[name]["errors"] += 1
                    continue

                scores[name].append(float(score))
                success = result.get("success")
                if success is None:
                    success = score >= metrics[name]["threshold"]
                metrics[name]["passed" if success else "failed"] += 1

        for name, metric_scores in scores.items():
            if metric_scores:
                metrics[name]["score"] = sum(metric_scores) / len(metric_scores)
        return metrics, data, "latest DeepEval run (partial metric coverage)"

    return empty_metrics(), {}, "no evaluation results"


def main():
    st.set_page_config(page_title="Agent Evaluation Dashboard", layout="wide")
    st.title("Agent Evaluation Dashboard")
    st.caption("Scores and passing rates for the seven agent evaluation metrics.")

    try:
        metrics, metadata, source = load_dashboard_results()
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as error:
        st.error(f"Could not read evaluation results: {error}")
        st.stop()

    st.caption(f"Data source: {source}")
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
