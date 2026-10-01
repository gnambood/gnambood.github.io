FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV ARTIFACT_DIR=/app/artifacts
WORKDIR /app
COPY api/requirements.txt /app/requirements.txt

# ECS deployment is CPU-only. Install the CPU PyTorch wheel explicitly to keep
# the container smaller and avoid pulling CUDA runtime packages.
RUN pip install --no-cache-dir --index-url https://download.pytorch.org/whl/cpu torch==2.5.1
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY api /app/api
RUN mkdir -p /app/artifacts
EXPOSE 8080
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8080"]
