FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

# 先装依赖（兼容 requirements.txt 或 requirements_digitalhub.txt）
COPY requirements*.txt /tmp/ 2>/dev/null || true
RUN python -m pip install -U pip && \
    if [ -f /tmp/requirements.txt ]; then pip install --no-cache-dir -r /tmp/requirements.txt; fi && \
    if [ -f /tmp/requirements_digitalhub.txt ]; then pip install --no-cache-dir -r /tmp/requirements_digitalhub.txt; fi

# 再拷源码
COPY . /app/

EXPOSE 9009

# 优先用你仓库里的 run_digitalhub.sh；若缺失则回退到 uvicorn（按你实际入口替换）
CMD bash -lc '\
  if [ -f ./run_digitalhub.sh ]; then \
    exec bash ./run_digitalhub.sh; \
  else \
    echo "[WARN] run_digitalhub.sh 未找到，回退 uvicorn（如入口不同请改）"; \
    exec python -m uvicorn digitalhub_service.app:app --host 0.0.0.0 --port 9009 --log-level info; \
  fi'
