import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from dotenv import load_dotenv

from deepeval import evaluate
from deepeval.evaluate import CacheConfig, DisplayConfig
from deepeval.integrations.langchain import CallbackHandler
from deepeval.metrics import (
    ArgumentCorrectnessMetric,
    GEval,
    PlanAdherenceMetric,
    PlanQualityMetric,
    StepEfficiencyMetric,
    TaskCompletionMetric,
    ToolCorrectnessMetric,
)
from deepeval.test_case import LLMTestCase, SingleTurnParams, ToolCall, ToolCallParams

if __package__:
    from .dataset import dataset
    from .model import eval_model
else:
    from dataset import dataset
    from model import eval_model


SUCCESSFUL_TASK_DESCRIPTION = """
If the username is missing, ask the user to provide it.
For a refund request, identify the customer and the requested purchases, and
check that each purchase is no more than 30 days old and is not in the future.
Refund only the items requested by the user. If the customer or requested item
cannot be found, do not issue a refund ticket and explain why.
Once the necessary information is available, tell the user whether a refund
ticket was issued and its amount, or explain why no refund was issued.
For an information-only request, answer the question without issuing a ticket.
"""

METRIC_THRESHOLDS = {
    "Task Completion": 0.8,
    "Step Efficiency": 0.8,
    "Plan Quality": 0.8,
    "Plan Adherence": 0.8,
    "Tool Correctness": 0.9,
    "Argument Correctness": 0.8,
    "Answer Correctness": 0.8,
}


def normalize_metric_name(name):
    if name.startswith("Answer Correctness"):
        return "Answer Correctness"
    return name


def write_dashboard_results(trace_result, single_turn_result, test_case_count):
    metric_results = {
        name: {
            "scores": [],
            "passed": 0,
            "failed": 0,
            "errors": 0,
            "threshold": threshold,
        }
        for name, threshold in METRIC_THRESHOLDS.items()
    }

    for evaluation_result in (trace_result, single_turn_result):
        for test_result in getattr(evaluation_result, "test_results", []) or []:
            for metric_data in test_result.metrics_data or []:
                name = normalize_metric_name(metric_data.name)
                if name not in metric_results:
                    continue

                result = metric_results[name]
                score = metric_data.score
                if score is None:
                    result["failed"] += 1
                    result["errors"] += 1
                    continue

                score = float(score)
                result["scores"].append(score)
                success = metric_data.success
                if success is None:
                    success = score >= result["threshold"]
                result["passed" if success else "failed"] += 1

    metrics = []
    for name, result in metric_results.items():
        scores = result.pop("scores")
        metrics.append(
            {
                "name": name,
                "average_score": sum(scores) / len(scores) if scores else None,
                "passed": result["passed"],
                "failed": result["failed"],
                "errors": result["errors"],
                "threshold": result["threshold"],
            }
        )

    report_path = Path(__file__).resolve().parent / ".deepeval" / ".latest_dashboard_results.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "test_case_count": test_case_count,
                "metrics": metrics,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def build_metrics():
    """Keep the thresholds and evaluator model used by the individual scripts."""
    trace_metrics = [
        TaskCompletionMetric(
            threshold=METRIC_THRESHOLDS["Task Completion"],
            model=eval_model,
            task=SUCCESSFUL_TASK_DESCRIPTION,
            include_reason=True,
        ),
        StepEfficiencyMetric(
            threshold=METRIC_THRESHOLDS["Step Efficiency"],
            model=eval_model,
            include_reason=True,
        ),
        PlanQualityMetric(
            threshold=METRIC_THRESHOLDS["Plan Quality"],
            model=eval_model,
            include_reason=True,
        ),
        PlanAdherenceMetric(
            threshold=METRIC_THRESHOLDS["Plan Adherence"],
            model=eval_model,
            include_reason=True,
        ),
    ]
    single_turn_metrics = [
        ArgumentCorrectnessMetric(
            threshold=METRIC_THRESHOLDS["Argument Correctness"],
            model=eval_model,
            include_reason=True,
        ),
        ToolCorrectnessMetric(
            threshold=METRIC_THRESHOLDS["Tool Correctness"],
            model=eval_model,
            include_reason=True,
            evaluation_params=[ToolCallParams.INPUT_PARAMETERS]
        ),
        GEval(
            name="Answer Correctness",
            evaluation_params=[
                SingleTurnParams.INPUT,
                SingleTurnParams.ACTUAL_OUTPUT,
                SingleTurnParams.EXPECTED_OUTPUT,
            ],
            evaluation_steps=[
                "Check that the actual output and expected output have the same "
                "logical conclusion about the user's request.",
            ],
            threshold=METRIC_THRESHOLDS["Answer Correctness"],
            model=eval_model,
            verbose_mode=True,
        ),
    ]
    return trace_metrics, single_turn_metrics


def main():
    load_dotenv()
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
    from agent import agent

    trace_metrics, single_turn_metrics = build_metrics()
    cache_config = CacheConfig(use_cache=False, write_cache=False)
    display_config = DisplayConfig(inspect_after_run=False)
    test_cases = []

    # The callback captures the trace required by the four agentic metrics.
    evaluation_iterator = iter(
        dataset.evals_iterator(
            metrics=trace_metrics,
            cache_config=cache_config,
            display_config=display_config,
        )
    )
    while True:
        try:
            golden = next(evaluation_iterator)
        except StopIteration as evaluation:
            trace_result = evaluation.value
            break

        response = agent.invoke(
            {"messages": [{"role": "user", "content": golden.input}]},
            config={
                "configurable": {"thread_id": str(uuid4())},
                "callbacks": [CallbackHandler()],
            },
        )

        tools_called = []
        for message in response["messages"]:
            for tool_call in getattr(message, "tool_calls", []) or []:
                tools_called.append(
                    ToolCall(
                        name=tool_call["name"],
                        input_parameters=tool_call["args"],
                    )
                )

        # Reuse the same response for the three remaining metrics. Keep these
        # cases local so repeated runs do not accumulate dataset.test_cases.
        test_cases.append(
            LLMTestCase(
                input=golden.input,
                actual_output=response["structured_response"].answer,
                expected_output=golden.expected_output,
                tools_called=tools_called,
                expected_tools=golden.expected_tools,
            )
        )

    single_turn_result = evaluate(
        test_cases=test_cases,
        metrics=single_turn_metrics,
        cache_config=cache_config,
        display_config=display_config,
    )
    write_dashboard_results(trace_result, single_turn_result, len(test_cases))
    print(f"\nCompleted all 7 metrics for {len(test_cases)} test cases.")


if __name__ == "__main__":
    main()