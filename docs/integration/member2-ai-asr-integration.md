# 成员 2 联调说明

## 责任边界

- 成员 2：接收音频、保存原声、校验用户权限、维护 `voice_id` 和业务状态。
- 成员 3：提供 ASR 识别结果和 AI 日记结构化结果。
- 成员 3 不直接写成员 2 的数据库，也不接收客户端的讯飞密钥。

## 推荐调用顺序

```text
客户端上传音频
  -> 成员 2 保存原声并生成 voice_id/event_id
  -> 成员 2 调用 POST /internal/ai/asr
  -> 成员 2 保存 transcript 和 ASR status
  -> 用户确认 transcript
  -> 成员 2 调用 POST /api/moments/generate
  -> 保存并展示 AI 返回的 moment JSON
```

ASR 调用契约见 `fuwai/ai/contracts/asr-https-integration.md`。AI 输出契约见 `fuwai/ai/contracts/moment.schema.json`。

## ASR 处理规则

1. `consent` 必须为 `true`，否则不调用或返回 `NO_CONSENT`。
2. 保存原声成功后，即使 ASR 失败也不能删除原声。
3. 只有 `status=completed` 且 `transcript` 非空时，才进入用户确认页面。
4. `ASR_TIMEOUT` 和 `ASR_PROVIDER_ERROR` 可以重试；`event_id` 必须保持不变以便幂等。
5. `INVALID_FORMAT`、`EMPTY_AUDIO`、`NO_CONSENT` 不应自动重试。

## AI 处理规则

请求：

```json
{
  "user_id": "user_001",
  "content": "用户确认后的转写文字",
  "voice_id": "voice_001",
  "bpm": 82
}
```

`content` 必须是用户确认后的文字，不要直接把未确认的 ASR 草稿交给 AI。`voice_id` 用于关联原声，`bpm` 只能作为背景信息。

响应 `data` 保留旧字段 `title`、`summary`、`ai_status`，并增加 `tags`、`suggested_replies`、`safety_flags`、`schema_version`。成员 2 应原样保存这些字段或保存完整 JSON，不要把 `summary` 覆盖 `raw_text`。

## 联调检查表

- [ ] 成员 2 能携带 `X-API-Key` 调用 ASR HTTPS 地址。
- [ ] `watch` 和 `pendant` 使用同一 ASR 路由，仅 `source` 不同。
- [ ] ASR 成功、失败和超时状态都能被成员 2 保存和展示。
- [ ] 用户确认前不会调用 `/api/moments/generate`。
- [ ] `/api/moments/generate` 返回合法 `moment.schema.json` 字段。
- [ ] 高风险内容含 `high_risk_content_review` 时不展示或自动发送建议回复。
- [ ] 联调使用脱敏音频、测试用户和临时 API Key。
