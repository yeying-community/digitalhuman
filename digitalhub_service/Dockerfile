FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}


# 先装依赖（如需额外 requirements.txt 可自行扩展）
COPY requirements_digitalhub.txt /tmp/requirements_digitalhub.txt
RUN python -m pip install -U pip && \
    pip install --no-cache-dir -r /tmp/requirements_digitalhub.txt

# 再拷源码，并让包结构保持在 /app/digitalhub_service
COPY . /app/digitalhub_service/
ENV PYTHONPATH=/app
WORKDIR /app

EXPOSE 9009

# 优先用你仓库里的 run_digitalhub.sh；若缺失则回退到 uvicorn（按你实际入口替换）
CMD bash -lc '\
  if [ -f /app/digitalhub_service/run_digitalhub.sh ]; then \
    exec bash /app/digitalhub_service/run_digitalhub.sh; \
  else \
    echo "[WARN] run_digitalhub.sh 未找到，回退 uvicorn（如入口不同请改）"; \
    cd /app && exec python -m uvicorn digitalhub_service.app:app --host 0.0.0.0 --port 9009 --log-level info; \
  fi'
