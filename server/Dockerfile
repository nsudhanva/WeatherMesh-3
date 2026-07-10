# WeatherMesh-3 real-time inference container (SageMaker Processing / any GPU host).
# Build from the repo root:  docker build -f server/Dockerfile -t wm3-pipeline .
# Weights are NOT baked in (1.2 GB) — they are fetched from S3 at runtime.
FROM nvidia/cuda:12.1.1-cudnn8-runtime-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive PATH="/root/.local/bin:${PATH}" \
    WM3_DEVICE=cuda UV_HTTP_TIMEOUT=300
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3.11 python3.11-venv python3-pip curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

WORKDIR /opt/wm3
# Only the code the model + pipeline need (no weights, no huge/ data, no .venv)
COPY pyproject.toml uv.lock utils.py meshes.py model.py ./
COPY model_latlon ./model_latlon
COPY constants ./constants
COPY server ./server

# Model deps (torch-cuda, natten via shi-labs allow-insecure-host, matepoint) + pipeline extras
RUN uv sync --no-group notebook \
    && uv pip install -r server/requirements-pipeline.txt

ENTRYPOINT ["uv", "run", "python", "-m", "server.wm3pipe.run_cycle"]
