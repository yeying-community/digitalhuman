FROM python:3.8-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements*.txt /tmp/ 2>/dev/null || true
RUN python -m pip install -U pip && \
    if [ -f /tmp/requirements.txt ]; then pip install --no-cache-dir -r /tmp/requirements.txt; fi

COPY . /app/

EXPOSE 8011

# 有 run.sh 就用它；否则请按你的入口改
CMD bash -lc '\
  if [ -f ./run.sh ]; then \
    exec bash ./run.sh; \
  else \
    echo "[WARN] run.sh 未找到，请提供启动脚本或修改为你的入口"; \
    exec python app/app.py; \
  fi'
