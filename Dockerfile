FROM python:3.14-slim

WORKDIR /evaluations

COPY pyproject.toml README.md */

COPY . .

RUN uv pip install --no-cache-dir 

EXPOSE 8080 
ENV PORT=8080 
ENV STREAMLIT_SERVER_PORT=8080
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

CMD ["streamlit", "run", "app.py"]