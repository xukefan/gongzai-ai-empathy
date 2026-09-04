# 成员 2 调用的 HTTPS ASR 接口

## 你需要交给成员 2 的信息

部署完成后，把下面三项通过私密渠道发给成员 2：

```text
ASR 服务地址：https://<你的域名>/internal/ai/asr
请求方法：POST
内部鉴权：X-API-Key: <内部共享密钥>
```

不要把 `IFLYTEK_API_KEY` 或 `IFLYTEK_API_SECRET` 发给成员 2；它们只配置在 ASR 服务端。

## 地址

```text
POST https://<ASR服务域名>/internal/ai/asr
Content-Type: multipart/form-data
X-API-Key: <内部调用密钥>
```

`<ASR服务域名>` 是部署 `ai/asr_api.py` 的 HTTPS 域名或网关地址。TLS 证书由 Nginx、Caddy、云负载均衡或 API 网关配置；成员 2 不需要也不应接触讯飞密钥。

## 请求字段

| 字段 | 类型 | 必填 | 示例 | 说明 |
|---|---|---:|---|---|
| `file` | file | 是 | `record.wav` | 支持 mp3/wav/pcm/opus/flac/ogg/speex，最大 500 MB |
| `event_id` | string | 是 | `event_001` | 业务事件唯一 ID；成员 2 用它做幂等键 |
| `source` | string | 是 | `watch` | 只能是 `watch` 或 `pendant` |
| `consent` | boolean | 是 | `true` | 必须为 `true`，表示用户已授权 |
| `language` | string | 否 | `zh-CN` | MVP 固定使用 `zh-CN`；服务内部映射为讯飞 `autodialect` |
| `recorded_at` | ISO 8601 string | 否 | `2026-09-02T10:00:00+08:00` | 业务记录时间，服务端暂不依赖 |

示例：

```bash
curl -X POST "https://asr.example.com/internal/ai/asr" \
  -H "X-API-Key: <部署负责人私下提供的密钥>" \
  -F "file=@record.wav" \
  -F "event_id=event_001" \
  -F "source=watch" \
  -F "consent=true" \
  -F "language=zh-CN"
```

## 成功响应（HTTP 200）

```json
{
  "request_id": "a7c1...",
  "event_id": "event_001",
  "status": "completed",
  "transcript": "今天答辩终于结束了。",
  "language": "zh-CN",
  "provider": "iflytek",
  "duration_ms": 12000,
  "error_code": null,
  "error_message": null,
  "schema_version": 1
}
```

## 失败响应

业务失败仍返回统一 JSON。`status` 可能为 `failed`、`invalid_audio`、`empty_transcript` 或 `unauthorized`；常见 `error_code` 为 `ASR_TIMEOUT`、`ASR_PROVIDER_ERROR`、`INVALID_FORMAT`、`FILE_TOO_LARGE`、`EMPTY_AUDIO`、`NO_CONSENT`、`INVALID_REQUEST`。网关校验失败时可能返回 HTTP 4xx：`401`（`X-API-Key` 缺失或错误）、`413`（文件超限）、`415`（格式不支持）、`422`（请求字段不合法）。

成员 2 可重试 `ASR_TIMEOUT` 和 `ASR_PROVIDER_ERROR`；不要自动重试 `NO_CONSENT`、`INVALID_FORMAT` 或空文件。相同 `event_id` 不应重复产生业务记录。

成员 2 可参考 `ai/asr_client_example.py`，调用前设置环境变量 `ASR_BASE_URL=https://<ASR服务域名>` 和 `ASR_INTERNAL_API_KEY=<内部共享密钥>`。示例使用 `requests` 发送 multipart 表单。

## 时延与语言

- 支持中文；业务字段传 `language=zh-CN`，服务内部使用讯飞 `autodialect`，可识别中英与中文方言。
- 讯飞是异步转写服务。当前服务会每 2 秒轮询一次，最长约 3 分钟；超时后返回 `ASR_TIMEOUT`。实际耗时取决于音频时长和讯飞排队状态，不能承诺固定平均值。

## 服务端启动

```powershell
pip install -r ai/requirements.txt
uvicorn ai.asr_api:app --host 127.0.0.1 --port 8001
```

生产环境把 `https://域名` 反向代理到 `http://127.0.0.1:8001`，并限制只有成员 2 的网关/服务可以访问 `/internal/ai/asr`。如果 ASR 路由已合并进成员 2 的 8000 端口后端，则按合并后的实际地址调整代理目标。讯飞 `APPID/APIKey/APISecret` 只配置在 ASR 服务的 `.env` 中。

Nginx 配置模板见 `ai/deploy/nginx-asr.conf.example`；证书路径与服务域名需要按实际服务器替换。
