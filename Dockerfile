FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md ./
COPY src ./src
COPY data ./data

RUN pip install --no-cache-dir . \
    && mkdir -p /app/data

EXPOSE 8000
CMD ["uvicorn", "app.index:app", "--host", "0.0.0.0", "--port", "8000"]
