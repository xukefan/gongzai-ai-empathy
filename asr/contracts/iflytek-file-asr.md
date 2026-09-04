# 讯飞录音文件转写大模型实现说明

本项目采用讯飞异步录音文件转写接口（文档版本：`Ifasr_llm`）。服务端流程为：

1. `POST https://office-api-ist-dx.iflyaisol.com/v2/upload`，请求体是原始音频二进制，返回 `content.orderId`。
2. 使用相同的 `signatureRandom`，向 `POST https://office-api-ist-dx.iflyaisol.com/v2/getResult` 轮询，直到 `content.orderInfo.status` 为 `4`（完成）或 `-1`（失败）。请求体必须是 `{}`。

鉴权使用 HMAC-SHA1 + Base64：将查询参数按自然顺序排序，跳过空值和 `signature`，对值进行 URL 编码后拼接，再用 `APISecret` 签名。最终签名只放在 HTTP `signature` 请求头，不放入 URL 查询串。

| 讯飞字段 | 项目配置 |
|---|---|
| `appId` | `IFLYTEK_APP_ID`（APPID） |
| `accessKeyId` | `IFLYTEK_API_KEY`（控制台 APIKey） |
| 签名密钥 | `IFLYTEK_API_SECRET`（控制台 APISecret） |
| 服务地址 | `IFLYTEK_BASE_URL`，默认 `https://office-api-ist-dx.iflyaisol.com` |

中文和方言自动识别使用 `language=autodialect`；多语种自动识别使用 `autominor`（需单独开通权限）。客户端默认关闭时长校验（`durationCheckDisable=true`），避免调用方必须先解析音频时长。文件限制遵循官方文档：16/8 kHz、16 bit、单声道，支持 `mp3/wav/pcm/opus/flac/ogg/speex`，最长 5 小时、最大 500 MB。

代码入口为 `ai/iflytek_file_asr.py`，统一业务响应入口为 `ai/asr_service.py`。APISecret 只能放在服务端 `.env`，不要提交到仓库或发送给成员 2。
