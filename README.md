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

### Deploying the dashboard to Databricks Apps

The dashboard reads the combined report from
`evaluations/.deepeval/.latest_dashboard_results.json` by default. The
`.deepeval` directory is git-ignored, so the report is not included when the
app is deployed from the repository.

To provide the report in Databricks, store
`.latest_dashboard_results.json` in a Unity Catalog volume, grant the app
permission to read that file, and set the app environment variable
`EVALUATION_RESULTS_PATH` to its full volume path, for example:

```text
/Volumes/<catalog>/<schema>/<volume>/.latest_dashboard_results.json
```

Alternatively, include the report at the default path in the app's deployed
files. The dashboard displays a warning if it cannot find the report.