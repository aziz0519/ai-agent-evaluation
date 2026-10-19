import logging
import sys
from pathlib import Path
from uuid import uuid4

sys.path.insert(
    0,
    str(Path(__file__).resolve().parents[1] / "agent")
)

from agent import agent 
from dataset import dataset 
from model import eval_model

from deepeval.metrics import PlanAdherenceMetric
from deepeval.integrations.langchain import CallbackHandler

logger = logging.getLogger(__name__)


metrics = [PlanAdherenceMetric(threshold=0.8,model=eval_model,include_reason=True)]

failed_examples = []
evaluation_iterator = iter(dataset.evals_iterator(metrics=metrics))
example_number = 0
while True:
    try:
        golden = next(evaluation_iterator)
    except StopIteration as evaluation:
        evaluation_result = evaluation.value
        break

    example_number += 1
    try:
        response = agent.invoke(
            {"messages": [{ "role": "user", "content" : golden.input }]},
            config={"configurable": {"thread_id": str(uuid4())},
            "callbacks": [CallbackHandler()]}
        )
    except Exception:
        logger.exception("Evaluation example %d failed during agent invocation", example_number)
        failed_examples.append(example_number)
        continue

failed_metric_examples = [
    (test_result.index, metric_result.score)
    for test_result in evaluation_result.test_results
    for metric_result in test_result.metrics_data or []
    if metric_result.name == metrics[0].__name__
    and metric_result.success is False
]

if failed_examples:
    logger.error("Agent invocation failed for examples: %s", failed_examples)

if failed_metric_examples:
    logger.error(
        "Plan adherence failed for examples (example, score): %s",
        failed_metric_examples,
    )

if failed_examples or failed_metric_examples:
    sys.exit(1)
