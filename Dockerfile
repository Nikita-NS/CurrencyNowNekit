FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# fonts-dejavu — чтобы Pillow мог рисовать кириллицу и ₽/€/¥
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY scripts ./scripts
COPY run.py .

# non-root
RUN useradd -m -u 10001 fxbot && chown -R fxbot:fxbot /app
USER fxbot

CMD ["python", "run.py"]
