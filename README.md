# Douyin NAS for fnOS

A small NAS-oriented service that uses the proven Douyin parsing/signature engine from [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API), then replaces the deployment/download layer with a safer fnOS-focused implementation.

## What this fork-layer changes

- x86_64 fnOS/Docker deployment with bridge networking; no host network and no privileged container.
- Strict Douyin-domain input validation and `X-API-Key` authentication.
- Enumerates `video.bit_rate` candidates instead of assuming `play_addr.url_list[0]` is the highest quality.
- Chooses `best`, or a requested `2160p` / `1440p` / `1080p` / etc. quality, with optional `h264` / `h265` preference.
- Downloads directly from the Douyin CDN to the NAS in a background task.
- Persistent task metadata in SQLite under `/data`.
- Configurable concurrency, maximum file size, and minimum free disk space.
- Cookie is supplied through `.env`; it is not committed to Git.

> "Best" means the highest-quality media variant returned by Douyin for the current account, IP, request profile and video. It cannot restore an author's pre-upload master if Douyin does not expose it.

## Quick start

```bash
git clone https://github.com/Rok1n/Quickstart-MahoganySquad-master.git douyin-nas
cd douyin-nas
cp .env.example .env
nano .env
mkdir -p /your/download/path /your/data/path
docker compose up -d --build
```

Open `http://NAS-IP:18080/health`. API docs are at `http://NAS-IP:18080/docs` when `DOCS_ENABLED=true`.

All `/api/v1/*` requests require:

```text
X-API-Key: <API_KEY from .env>
```

### Parse and inspect all returned qualities

```bash
curl -X POST 'http://NAS-IP:18080/api/v1/parse' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{"url":"https://v.douyin.com/xxxx/","quality":"best","codec":"auto"}'
```

### Create a NAS download task

```bash
curl -X POST 'http://NAS-IP:18080/api/v1/downloads' \
  -H 'Content-Type: application/json' \
  -H 'X-API-Key: YOUR_KEY' \
  -d '{"url":"https://v.douyin.com/xxxx/","quality":"best","codec":"auto"}'
```

Then query:

```bash
curl -H 'X-API-Key: YOUR_KEY' \
  'http://NAS-IP:18080/api/v1/downloads/TASK_ID'
```

Completed files are organized as:

```text
/downloads/<author>/<YYYY-MM-DD>/<description>_<aweme_id>_<quality>_<codec>.mp4
```

## fnOS permissions

The compose file runs the container as `${PUID}:${PGID}`. On fnOS, SSH into the NAS and determine your UID/GID with `id`. Ensure both host directories in `.env` are writable by that account.

## Cookie

Douyin may return no detail or lower-quality variants when requests are unauthenticated or risk-controlled. Set `DOUYIN_COOKIE` to the Cookie request header from a logged-in `douyin.com` browser session. Do not commit `.env`.

## Security

Do not expose port 18080 directly to the public Internet. For remote use, place it behind your own authenticated reverse proxy or VPN/Tailscale-equivalent layer. The built-in API key is a second line of defense, not a complete Internet perimeter.

## Upstream dependency

The Dockerfile pins the upstream parser/signature engine using `UPSTREAM_REF`. This project intentionally does not duplicate its `a_bogus` implementation. When Douyin changes request signing, update `UPSTREAM_REF`, rebuild, and test `/api/v1/parse` before changing the NAS service layer.

Upstream project: Evil0ctal/Douyin_TikTok_Download_API, Apache-2.0 licensed.
