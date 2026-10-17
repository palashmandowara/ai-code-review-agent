FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY review_agent ./review_agent
RUN pip install --no-cache-dir .
CMD ["uvicorn", "review_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
