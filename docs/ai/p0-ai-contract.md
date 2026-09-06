# P0 AI 输入输出与联调契约（DeepSeek v4 Flash）

当前模型：`deepseek-v4-flash`。调用由后端服务端完成，客户端不直接调用 DeepSeek。

## 1. 当前实现

成员 2 的后端调用 `POST /api/moments/generate`。服务端只接收用户确认后的转写文字，AI 不读取原始录音。

请求最小字段：

```json
{
  "user_id": "user-a",
  "content": "今天答辩终于结束了。"
}
```

推荐完整字段：

```json
{
  "user_id": "user-a",
  "content": "今天答辩终于结束了，虽然有点乱，但现在松了一口气。",
  "voice_id": "voice-001",
  "event_id": "event-001",
  "recorded_at": "2026-09-06T15:30:00+08:00",
  "bpm": 82,
  "consent": true,
  "schema_version": 1
}
```

`consent=true` 是调用方对“用户已确认并授权 AI 使用该文字”的声明。当前原型路由仍由成员 2 负责认证和授权；在正式联调前，成员 2 必须在网关校验该字段或使用等价的授权状态。

## 2. 成功响应

`data` 中包含以下字段：

```json
{
  "title": "答辩结束后的记录",
  "summary": "今天答辩有些混乱，但结束后松了一口气。",
  "tags": ["学习", "答辩"],
  "suggested_replies": ["辛苦了，结束了就好。"],
  "safety_flags": [],
  "ai_status": "generated",
  "schema_version": 1,
  "prompt_version": "moment-v1"
}
```

`summary` 只能压缩 `content` 中的事实。`suggested_replies` 只是草稿，必须由用户主动选择后才能发送。无模型密钥时 `ai_status=fallback`，不能显示为真实生成成功。

完整字段约束见 `fuwai/ai/contracts/ai-moment-request.schema.json` 和 `moment.schema.json`。

## 3. 错误处理

| HTTP | code | retryable | 调用方动作 |
|---:|---|:---:|---|
| 422 | `AI_INVALID_REQUEST` | 否 | 修正空文本、超长文本或 BPM |
| 403 | `AI_CONSENT_REQUIRED` | 否 | 先让用户确认并授权转写文字 |
| 502 | `AI_PROVIDER_UNAVAILABLE` | 是 | 保留原文，稍后重试 |
| 504 | `AI_TIMEOUT` | 是 | 保留原文，指数退避重试 |
| 502 | `AI_INVALID_RESPONSE` | 是 | 记录失败，不展示伪造成功 |
| 502 | `AI_OUTPUT_SCHEMA_INVALID` | 是 | 服务端已自动重试一次，仍失败则人工/稍后重试 |

错误 JSON 结构见 `fuwai/ai/contracts/ai-error.schema.json`。错误响应不得包含 API Key、原始录音 URL 或完整健康数据。

## 4. 端到端联调顺序

```text
POST /api/voice/upload
  -> ASR 完成并返回 transcript
  -> 用户确认 transcript 且 consent=true
  -> POST /api/moments/generate
  -> 成员 2 将 raw_text、voice_id、AI 输出关联保存
  -> 客户端展示 title/summary/tags/suggested_replies/safety_flags
```

成员 2 需要确认并回填：

- `voice_id` 与 `moment_id` 的关联字段；
- ASR 状态持久化字段和重试策略；
- AI 输出字段保存方式（建议 JSON 列或独立字段）；
- `event_id` 是否作为幂等键；
- 正式 HTTPS 域名、内部 API 鉴权方式和超时值。

## 5. 配置

仓库只提交 `backend/.env.example`。部署环境需要由负责人安全注入：

```text
AI_API_BASE_URL=<OpenAI-compatible base URL>
AI_API_KEY=<secret, never commit>
AI_MODEL=<provider model name>
AI_TIMEOUT_SECONDS=30
AI_PROMPT_VERSION=moment-v1
```

当前适配器使用 OpenAI-compatible Chat Completions 协议。如果最终使用的供应商不是该协议，需要由成员 3 增加 provider adapter，而不是修改客户端或把密钥放入仓库。
