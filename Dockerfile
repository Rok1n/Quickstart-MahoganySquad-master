FROM python:3.11-slim-bookworm

ARG UPSTREAM_REF=42784ffc83a72a516bfe952153ad7e2a3998d16c

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/douyin-upstream:/srv

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*

RUN git clone https://github.com/Evil0ctal/Douyin_TikTok_Download_API.git /opt/douyin-upstream \
    && cd /opt/douyin-upstream \
    && git checkout "$UPSTREAM_REF" \
    && rm -rf .git

WORKDIR /srv
COPY requirements.txt /srv/requirements.txt
RUN pip install --no-cache-dir -r /opt/douyin-upstream/requirements.txt \
    && pip install --no-cache-dir -r /srv/requirements.txt

COPY app /srv/app

EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080", "--proxy-headers"]
