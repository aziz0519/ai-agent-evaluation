# Agent Evaluation Suite using DeepEval
> Evaluate agent metrics such as task completion and tool correctness on a sample customer refund agent using DeepEval

## Problem Statement
* AI Agents cannot evaluate their own task success
* Refund agent can submit inaccurate refund amount
* Unauthorized user can request for refund for items they did not purchase 


## Evaluation Metrics
* **Task completion:** Did the agent accomplish the user's task?
* **Step efficiency:** Did it avoid redundant and unnecessary steps?
* **Plan quality:** Was the plan suitable to the task?
* **Plan adherence:** Did it execution follow the plan?
* **Tool correctness:** Did it call the expected tools?
* **Argument correctness:** Argument correctness
* **Answer correctness:** Did its final answer reach the expected conclusion?

## Evaluation Dashboard
Run the combined evaluation to create a dashboard report, then launch Streamlit:

```bash
uv run python evaluations/eval_all.py
uv run streamlit run evaluations/streamlit_ui.py
```

The dashboard shows the average score and the passed/failed case counts for
each metric. It can also display available metrics from the latest DeepEval run
when a combined dashboard report has not been generated yet.