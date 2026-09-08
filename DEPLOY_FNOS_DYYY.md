# 飞牛 fnOS x86 部署 DYYY 抖音原画解析 API 教程

## 1. 最终目标

这套服务的职责只有一个：**NAS 接收抖音分享链接，解析出抖音当前提供的最高可得视频直链，然后把直链作为 JSON 返回给 DYYY。**

NAS 不下载视频、不保存视频、不转码，也不把视频数据代理给手机。真正的视频下载发生在 iPhone/DYYY 与抖音 CDN 之间。

最终给 DYYY 填写的接口可以是：

```text
https://你的域名/dy.php?url=
```

如果接口会暴露到公网，更推荐：

```text
https://你的域名/dy.php?token=你的随机密钥&url=
```

调用链如下：

```text
DYYY
  │
  │ GET /dy.php?url=<抖音分享链接>
  ▼
你的域名 / HTTPS
  │
  ▼
反向代理
  │
  ▼
fnOS:18080
  │
  ▼
Douyin Parser 容器
  │
  ├─ 解析 aweme_id
  ├─ 请求抖音作品详情
  ├─ 遍历 video.bit_rate[]
  ├─ 按分辨率 → 码率 → 文件大小排序
  └─ 返回最高质量 CDN URL
  │
  ▼
DYYY 直接从抖音 CDN 下载
```

## 2. 为什么这个版本适配 DYYY

DYYY 的“接口解析保存媒体”并不是要求一个标准 REST API Key。它实际保存的是一个**接口 URL 前缀**，调用时把分享链接 URL 编码后直接追加到该字符串后面，因此接口必须支持 GET 查询参数形式。

本项目提供：

```text
GET /dy.php?url=<抖音链接>
```

成功返回：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "video_url": "https://抖音CDN/最高质量视频",
    "video": "https://抖音CDN/最高质量视频",
    "url": "https://抖音CDN/最高质量视频",
    "video_list": [
      {
        "url": "https://抖音CDN/4K候选",
        "level": "2160p / H265 / 12.0Mbps"
      },
      {
        "url": "https://抖音CDN/1080P候选",
        "level": "1080p / H264 / 6.0Mbps"
      }
    ],
    "cover": "https://封面地址",
    "music": "https://音乐地址"
  }
}
```

这样 DYYY 在普通模式下可直接使用 `video_url`，开启“接口显示清晰选项”后又可以读取 `video_list`。

## 3. 准备条件

需要：

- 飞牛 fnOS x86 NAS
- 已安装 Docker
- 可以 SSH 登录 NAS
- NAS 可以访问 GitHub 和抖音
- 一个已登录抖音网页端取得的 Cookie
- 如果需要公网使用：一个域名和 HTTPS 入口

先 SSH 登录 NAS，并确认 Docker：

```bash
docker --version
docker compose version
```

## 4. 拉取项目

选择 NAS 上用于保存 Docker 项目的目录。例如：

```bash
mkdir -p /vol1/1000/Docker
cd /vol1/1000/Docker
```

如果你的实际卷路径不是 `/vol1/1000`，请用自己的路径。

拉取仓库：

```bash
git clone https://github.com/Rok1n/Quickstart-MahoganySquad-master.git douyin-parser
cd douyin-parser
```

以后更新代码只需要：

```bash
cd /vol1/1000/Docker/douyin-parser
git pull
docker compose up -d --build
```

## 5. 创建配置文件

复制模板：

```bash
cp .env.example .env
nano .env
```

推荐配置：

```env
PORT=18080
TZ=Asia/Shanghai

DOUYIN_COOKIE=这里填写你的抖音Cookie

COMPAT_TOKEN=这里填写随机密钥

DEFAULT_QUALITY=best
DEFAULT_CODEC=auto

HTTP_PROXY=
HTTPS_PROXY=

DOCS_ENABLED=true

UPSTREAM_REF=42784ffc83a72a516bfe952153ad7e2a3998d16c
```

### 5.1 生成接口 Token

公网部署强烈建议设置 `COMPAT_TOKEN`：

```bash
openssl rand -hex 32
```

把生成的 64 位十六进制字符串填到：

```env
COMPAT_TOKEN=生成的随机字符串
```

如果 `COMPAT_TOKEN` 留空，`/dy.php` 将不需要认证。只建议在纯局域网环境这样做。

### 5.2 获取 DOUYIN_COOKIE

电脑浏览器登录：

```text
https://www.douyin.com
```

打开开发者工具 → Network，刷新网页，选择一个发往 `douyin.com` 的请求，在 Request Headers 中找到：

```text
Cookie: xxx=...; yyy=...; zzz=...
```

只复制 `Cookie:` 后面的内容，填入：

```env
DOUYIN_COOKIE=xxx=...; yyy=...; zzz=...
```

不要把 `.env` 上传到 GitHub。

## 6. 构建并启动

执行：

```bash
docker compose build --no-cache
docker compose up -d
```

查看状态：

```bash
docker compose ps
```

查看日志：

```bash
docker compose logs -f douyin-parser
```

容器使用普通 bridge 网络，不使用 `host` 网络，不使用 `privileged`，并以只读根文件系统运行。NAS 不需要创建任何视频下载目录。

## 7. 健康检查

局域网访问：

```text
http://你的NAS-IP:18080/health
```

正常结果类似：

```json
{
  "ok": true,
  "mode": "parser-only",
  "cookie_configured": true,
  "compat_token_configured": true,
  "default_quality": "best",
  "default_codec": "auto"
}
```

如果 `cookie_configured` 是 `false`，说明 `.env` 中的 Cookie 没有正确进入容器。

## 8. 在局域网先测试解析

没有设置 Token 时：

```bash
curl -G 'http://你的NAS-IP:18080/dy.php' \
  --data-urlencode 'url=https://v.douyin.com/你的短链/'
```

设置了 Token 时：

```bash
curl -G 'http://你的NAS-IP:18080/dy.php' \
  --data-urlencode 'token=你的COMPAT_TOKEN' \
  --data-urlencode 'url=https://v.douyin.com/你的短链/'
```

正确结果必须至少满足：

```json
{
  "code": 200,
  "data": {
    "video_url": "https://..."
  }
}
```

如果视频确实存在多个候选，还会看到：

```json
"video_list": [
  {"level": "2160p / H265 / ...", "url": "..."},
  {"level": "1080p / H264 / ...", "url": "..."}
]
```

## 9. “原画”是如何选择的

服务不是简单读取 `play_addr.url_list[0]`。它优先遍历：

```text
aweme_detail.video.bit_rate[]
```

从每个候选读取：

- 宽度
- 高度
- 码率
- 数据大小
- 编码类型
- `play_addr.url_list`

默认 `best` 按以下顺序排序：

```text
像素数量（width × height）
        ↓
码率 bitrate
        ↓
数据大小 data_size
```

因此如果抖音返回 2160p、1440p、1080p，默认选择 2160p；如果同分辨率有多个候选，再选择码率更高的版本。

需要注意：“原画”在这里指**抖音当前向这个 Cookie、IP、请求环境暴露的最高可得源流**，不是作者上传前的原始母版。如果抖音只返回 1080p，API 不能凭空恢复 4K。

## 10. 配置域名和 HTTPS

DYYY 最终最好访问 HTTPS，而不是直接访问 NAS 的 `18080` 端口。

假设：

```text
NAS 局域网 IP：192.168.1.100
Parser 端口：18080
你的域名：dy.example.com
```

反向代理的上游只需要指向：

```text
http://192.168.1.100:18080
```

外部则提供：

```text
https://dy.example.com
```

路径不需要改写，因此：

```text
https://dy.example.com/dy.php?url=...
```

会原样代理到：

```text
http://192.168.1.100:18080/dy.php?url=...
```

如果你已经有 Nginx、Nginx Proxy Manager、Caddy、Traefik 或其他反向代理，只需建立上述 upstream 映射并配置证书即可。

飞牛 fnOS 新版本的系统 Web 服务本身可能占用或重定向 80/443，因此不要为了本项目直接让 Docker 容器抢占宿主机 80/443。推荐让解析器继续只监听 `18080`，由已有反向代理或路由器端口映射负责公网 HTTPS。

如果使用 DDNS，域名应解析到你的公网地址；如果没有公网 IPv4，也可以使用支持 HTTPS 的隧道/反向代理方案。由于本服务只返回 JSON，视频本身仍由 DYYY 直接从抖音 CDN 获取，因此解析服务的流量很小。

## 11. 在 DYYY 中填写接口

进入 DYYY 设置，找到：

```text
接口解析保存媒体
```

### 无 Token

填写：

```text
https://dy.example.com/dy.php?url=
```

### 有 Token（推荐）

填写：

```text
https://dy.example.com/dy.php?token=你的COMPAT_TOKEN&url=
```

注意最后必须保留：

```text
url=
```

不要在后面自己填写抖音链接。DYYY 会在真正调用时自动把当前作品的分享链接追加到它后面。

如果希望 DYYY 显示 API 返回的多个清晰度候选，再开启：

```text
接口显示清晰选项
```

如果只希望点击后直接拿最高质量，则保持默认即可，服务会通过 `video_url` 返回 `best`。

## 12. 最终接口示例

DYYY 中保存：

```text
https://dy.example.com/dy.php?token=abc123&url=
```

DYYY 实际请求会类似：

```text
https://dy.example.com/dy.php?token=abc123&url=https%3A%2F%2Fv.douyin.com%2Fxxxxxx%2F
```

服务返回：

```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "video_url": "https://抖音CDN/最高质量.mp4",
    "video_list": [
      {
        "url": "https://抖音CDN/2160p.mp4",
        "level": "2160p / H265 / 12.3Mbps"
      },
      {
        "url": "https://抖音CDN/1080p.mp4",
        "level": "1080p / H264 / 5.8Mbps"
      }
    ]
  }
}
```

NAS 的工作到这里结束。之后 DYYY 直接访问 `video_url` 或用户选择的 `video_list[].url` 下载视频。

## 13. 常见问题

### 返回 `code: 502` 或提示没有 `aweme_detail`

优先更新 `DOUYIN_COOKIE`，然后：

```bash
docker compose restart douyin-parser
```

再查看：

```bash
docker compose logs --tail=200 douyin-parser
```

### 只有 1080p，没有 2K/4K

先查看返回的 `video_list`。如果列表里只有 1080p，说明抖音这次没有向当前 Cookie/IP/请求环境提供更高候选，不是 NAS 下载或转码造成的降画质。

### DYYY 提示接口返回数据为空

确认返回结构是：

```text
code = 200
data = {...}
```

并确认至少有：

```text
data.video_url
```

### DYYY 无法访问 HTTP 接口

优先改成 HTTPS 域名。iOS 网络策略、证书和公网 NAT 都可能导致裸 HTTP/内网地址不可用。

### 公网接口被别人刷

设置 `COMPAT_TOKEN`，然后把 DYYY 接口改成：

```text
https://你的域名/dy.php?token=随机密钥&url=
```

必要时再在反向代理层增加速率限制。

## 14. 更新项目

更新我们自己的服务代码：

```bash
cd /vol1/1000/Docker/douyin-parser
git pull
docker compose up -d --build
```

项目固定使用一个上游抖音解析内核 commit，避免某天 `docker build` 自动拿到不同源码。如果以后抖音接口变化，需要升级上游内核时，再明确修改 `.env` 中的：

```env
UPSTREAM_REF=新的commit SHA
```

然后重新构建：

```bash
docker compose build --no-cache
docker compose up -d
```

## 15. 推荐的最终配置

对于“fnOS NAS 只做解析 + DYYY 下载”的用途，推荐：

```env
PORT=18080
TZ=Asia/Shanghai
DOUYIN_COOKIE=你的Cookie
COMPAT_TOKEN=一个64位随机字符串
DEFAULT_QUALITY=best
DEFAULT_CODEC=auto
HTTP_PROXY=
HTTPS_PROXY=
DOCS_ENABLED=false
UPSTREAM_REF=42784ffc83a72a516bfe952153ad7e2a3998d16c
```

最终 DYYY 填写：

```text
https://你的域名/dy.php?token=你的COMPAT_TOKEN&url=
```

这就是本项目针对你的实际用途设计的最终工作模式。
