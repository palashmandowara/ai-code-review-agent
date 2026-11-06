FROM node:22-alpine AS frontend
WORKDIR /build/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml README.md ./
COPY review_agent ./review_agent
COPY --from=frontend /build/review_agent/static ./review_agent/static
RUN pip install --no-cache-dir .
CMD ["uvicorn", "review_agent.api:app", "--host", "0.0.0.0", "--port", "8000"]
