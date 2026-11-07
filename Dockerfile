FROM python:3.14-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /uvx /bin/

WORKDIR /evaluations

COPY pyproject.toml README.md */

COPY . .

RUN uv sync --locked --no-install-project

EXPOSE 8080 
ENV PORT=8080 
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV PATH="/evaluations/.venv/bin:$PATH"

CMD ["streamlit", "run", "evaluations/streamlit_ui.py"]