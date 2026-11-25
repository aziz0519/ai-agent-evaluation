# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Dependencies and the interpreter are managed by `uv` (Python `>=3.14`, pinned in `.python-version`).

```bash
uv sync --locked                      # install exactly what uv.lock pins
uv run python evaluations/eval_all.py # run all 7 metrics, write the dashboard report
uv run streamlit run evaluations/streamlit_ui.py
```

<!-- coderabbit-ai-generated:v1 -->

<!-- coderabbit-ai-generated-section:v1:775cb0adcf727ee2d755ae54340f37c76d87be49ad2b9e718f05a1dc20a3dade -->

Install the development dependencies and run the pytest suite:

```bash
uv sync --locked --extra dev
uv run pytest
```

Pytest deselects tests marked `integration` by default. To run only those tests, export
`OPENAI_API_KEY` and run `uv run pytest -m integration`.

To run a single DeepEval metric directly, use `uv run python evaluations/task_completion.py`.

<!-- /coderabbit-ai-generated:v1 -->

Linting uses Ruff, and it is enforced in CI:

```bash
uv run --with ruff ruff check .       # CI runs `.venv/bin/ruff check .`
uv run --with ruff ruff format .
```

CI (`.github/workflows/ci.yml`) runs `uv sync --locked`, then Ruff, then `docker build`.

## Required environment

- `OPENAI_API_KEY` in `.env` (see `.env.example`). Both `agent/models.py` and
  `evaluations/model.py` call `load_dotenv()` and use the model string `gpt-6-luna`.
- The evaluator model is a single string in `evaluations/model.py` (`eval_model`), not a client object.
  Every metric script and `eval_all.py` import it, so changing the judge model is a one-line change.

## Architecture

There are two halves that only meet through LangChain callbacks.

`agent/` is a LangChain/LangGraph customer refund agent built by `create_agent` in `agent/agent.py`.
It has four tools in `agent/tools.py` (`get_user_purchase_history`, `get_today_date`,
`calculate_right_refund`, `issue_refund_ticket`), a structured output object in `agent/objects.py`, a
system prompt in `agent/prompts.py`, and a static fixture dataset in `agent/data.py`. `issue_refund_ticket`
is a stub that only returns a string, so refund amounts are never actually charged and the data is
read-only.

`evaluations/` scores that agent with DeepEval. `evaluations/dataset.py` holds the goldens: an input, an
expected output, and the ordered `expected_tools` with their input parameters.

### The two evaluation passes

`evaluations/eval_all.py` is the important structure. The seven metrics split into two kinds that DeepEval
consumes differently, and the script runs them in one agent pass:

1. Trace metrics (Task Completion, Step Efficiency, Plan Quality, Plan Adherence) are driven by
   `dataset.evals_iterator()`. The agent is invoked inside the iterator loop with a
   `deepeval.integrations.langchain.CallbackHandler()`, which is what captures the trace those four
   metrics need. The iterator must be drained with `next()` in a loop and read via
   `StopIteration.value`, because the aggregate result is only available after it finishes.
2. Single-turn metrics (Argument Correctness, Tool Correctness, Answer Correctness) are evaluated in a
   second `evaluate()` call over `LLMTestCase`s built from the exact same responses. The tool calls are
   re-extracted from `response["messages"]` into `ToolCall` objects.

Those `LLMTestCase`s are deliberately built as a local list rather than appended to `dataset.test_cases`,
so repeated runs do not accumulate state on the shared dataset object.

The report written by `write_dashboard_results()` to `evaluations/.deepeval/.latest_dashboard_results.json`
is what `streamlit_ui.py` renders. `METRIC_THRESHOLDS` is duplicated in `evaluations/eval_all.py`,
`evaluations/streamlit_ui.py`, and the individual metric scripts, so a threshold change has to be made in
each place.

### Import layout gotcha

`agent/` and `evaluations/` have no `__init__.py`. Modules inside each directory import their siblings by
bare name (`from models import model`, `from dataset import dataset`). Because of that, every script that
crosses the boundary inserts the repo root's `agent/` directory onto `sys.path` before importing
`agent`. `evaluations/eval_all.py` additionally uses an `if __package__:` guard to support both package
and flat execution. Do not "fix" these imports to be dotted paths without updating the `sys.path`
insertions; the flat sibling style is what makes `uv run python evaluations/eval_all.py` work from the repo
root.

### Ruff baseline

`pyproject.toml` carries a `[tool.ruff.lint.per-file-ignores]` baseline of pre-existing violations, mostly
`I001` import sorting in the older scripts. New code should pass Ruff without adding an entry to that list.

## Dashboard deployment

The `.deepeval/` directory is gitignored, so the report file is absent in a fresh clone until
`eval_all.py` runs, and it is not shipped when the app is deployed. `streamlit_ui.py` falls back to default
report locations and shows a warning instead of crashing when the configured report cannot be read.

For Databricks Apps, publish the report to a Unity Catalog volume and set `EVALUATION_RESULTS_PATH` to the
volume path, for example `/Volumes/<catalog>/<schema>/<volume>/.latest_dashboard_results.json`. Locally the
same variable, or `.streamlit/secrets.toml`, selects the report path. `Dockerfile` builds an image whose
`CMD` runs the Streamlit dashboard on port 8080.
