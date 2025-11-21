FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ENV PIP_INDEX_URL=${PIP_INDEX_URL}

COPY requirements.txt /tmp/requirements.txt
RUN python -m pip install -U pip && \
    pip install --no-cache-dir -r /tmp/requirements.txt

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
