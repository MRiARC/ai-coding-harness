FROM python:3.12-slim
WORKDIR /workspace
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY config.example.yaml ./
RUN pip install --no-cache-dir -e ".[platform]"
EXPOSE 8000
CMD ["uvicorn", "harness.service.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
