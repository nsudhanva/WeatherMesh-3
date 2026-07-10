# WeatherMesh-3 real-time inference container (SageMaker Processing / any GPU host).
# Build from the repo root:  docker build -f server/Dockerfile -t wm3-pipeline .
# Weights are NOT baked in (1.2 GB) — fetched from S3 at runtime.
# Base already ships Python 3.11 + torch 2.5.1 + CUDA 12.1, so no apt / no torch reinstall.
FROM pytorch/pytorch:2.5.1-cuda12.1-cudnn9-runtime

ENV WM3_DEVICE=cuda PIP_ROOT_USER_ACTION=ignore PIP_NO_CACHE_DIR=1
WORKDIR /opt/wm3

COPY pyproject.toml utils.py meshes.py model.py ./
COPY model_latlon ./model_latlon
COPY constants ./constants
COPY server ./server

# natten (CUDA neighborhood attention; shi-labs cert is expired -> trusted-host),
# matepoint (test.pypi), and the pipeline deps.
RUN pip install "natten==0.17.3+torch240cu121" \
        --find-links https://shi-labs.com/natten/wheels/ --trusted-host shi-labs.com \
    && pip install "matepoint" \
        --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple/ \
    && pip install -r server/requirements-pipeline.txt

ENTRYPOINT ["python", "-m", "server.wm3pipe.run_cycle"]
