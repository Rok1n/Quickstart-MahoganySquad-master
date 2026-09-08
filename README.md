# Douyin Original Parser for fnOS + DYYY

这是一个面向飞牛 fnOS x86 NAS 的**纯解析服务**。NAS 只负责解析抖音分享链接并返回抖音 CDN 的直接媒体 URL，不代理、不转码、不保存视频文件。

核心用途是给 DYYY 提供如下形式的解析接口：

```text
https://你的域名/dy.php?url=
```

公网部署建议使用：

```text
https://你的域名/dy.php?token=你的密钥&url=
```

DYYY 会把分享链接 URL 编码后直接追加到这个接口前缀。

## DYYY 兼容返回

成功时：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "video_url": "https://...douyin-cdn.../video.mp4",
    "video": "https://...douyin-cdn.../video.mp4",
    "url": "https://...douyin-cdn.../video.mp4",
    "video_list": [
      {
        "url": "https://...",
        "level": "2160p / H265 / 12.0Mbps"
      }
    ],
    "cover": "https://...",
    "music": "https://..."
  }
}
```

`video_url` 默认指向抖音当前返回候选中分辨率最高、随后码率最高的源。`video_list` 保留全部候选，供 DYYY 的“接口显示清晰选项”使用。

## 架构

```text
DYYY / iPhone
    |
    | GET https://domain/dy.php?url=<share-link>
    v
fnOS Docker: douyin-parser
    |
    | 只请求作品元数据
    v
Douyin Web API
    |
    | 返回 bit_rate / play_addr
    v
最高画质选择器
    |
    | JSON 返回直接 CDN URL
    v
DYYY 直接从抖音 CDN 下载
```

NAS 本身不会承载视频下载流量，也不需要视频下载目录。

## 快速部署

完整教程见 [DEPLOY_FNOS_DYYY.md](./DEPLOY_FNOS_DYYY.md)。

```bash
git clone https://github.com/Rok1n/Quickstart-MahoganySquad-master.git douyin-parser
cd douyin-parser
cp .env.example .env
nano .env
docker compose up -d --build
```

健康检查：

```text
http://NAS-IP:18080/health
```

本地接口测试：

```bash
curl -G 'http://NAS-IP:18080/dy.php' \
  --data-urlencode 'url=https://v.douyin.com/你的短链/'
```

## 原画选择规则

服务优先读取抖音作品详情中的 `video.bit_rate[]`，遍历各候选的 `play_addr`，再按以下顺序选择：

1. 像素数量（宽 × 高）
2. 码率
3. 数据大小

因此 `best` 的准确含义是：**抖音当前向该 Cookie、IP 和请求环境暴露的最高可得源流**。它不等同于作者上传前的母版；如果抖音本次只返回 1080p，服务无法凭空生成 2K/4K。

## 安全

输入仅接受 `douyin.com`、`v.douyin.com` 和 `iesdouyin.com` 域名。公网部署强烈建议设置 `COMPAT_TOKEN`，并使用 HTTPS。

本项目的抖音请求内核基于 `Evil0ctal/Douyin_TikTok_Download_API`，Docker 构建时固定上游 commit，避免构建结果随上游变化而不可复现。
