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
  "event_id": "event_001",
  "bpm": 82,
  "consent": true
}
```

`content` 必须是用户确认后的文字，`consent` 必须为 `true`；缺少授权声明时后端返回 `AI_CONSENT_REQUIRED`。`voice_id` 用于关联原声，`event_id` 用于幂等处理，`bpm` 只能作为背景信息。

响应 `data` 保留旧字段 `title`、`summary`、`ai_status`，并增加 `tags`、`suggested_replies`、`safety_flags`、`schema_version`、原始/确认转写和事件字段。完整记录结构见 `fuwai/ai/contracts/life-moment-record.schema.json`。后端会持久化这些生活瞬间字段；成员 2 不要把 `summary` 覆盖 `raw_text`。

## 共同时间线（4.6.2）

生活瞬间保存后默认仍是私有的。记录拥有者确认转写后，通过以下接口显式分享：

```text
POST /api/moments/{moment_id}/share?user_id=user_001
```

只有记录所属用户可以分享；没有 active 关系、未确认转写或已归档记录都会被拒绝。双方读取共同时间线：

```text
GET /api/timeline?user_id=user_001&limit=20&offset=0
```

响应 `data.moments` 只包含双方已分享、已确认且未归档的完整生活瞬间，并按 `recorded_at` 倒序；`event_id`、`voice_id` 和确认转写保留用于回溯。解除关系后读取返回 `TIMELINE_RELATIONSHIP_REQUIRED`，不会泄露历史共享记录。

## 共同回顾（4.6.3）

```text
GET /api/recaps/week?user_id=user_001&anchor_date=2026-09-16
GET /api/recaps/month?user_id=user_001&anchor_date=2026-09-16
GET /api/recaps/anniversary?user_id=user_001&anchor_date=2026-09-16
```

`anchor_date` 可省略用于周报和月报，服务端默认当天；纪念日回顾必须提供该日期，并匹配历史上相同月日的共同记录。输出契约为 `fuwai/ai/contracts/recap-response.schema.json`：`fact_summary` 是由片段数量、日期和已保存标签组成的事实性汇总，`representative_events` 和 `source_event_ids` 用于回到原记录核验。不要把结果展示为关系评价、情绪诊断或自动生成的共同经历。

## 记忆检索（4.6.4）

```text
GET /api/memories/search?user_id=user_001&query=答辩结束后的片段&limit=20
```

检索只在双方已确认、已分享、未归档的共同记录内完成。服务端返回的 `results` 带 `event_id`、确认转写、标签、`matched_fields` 和 `score`，以便客户端定位原记录；当前 `search_method=local_lexical_semantic_v1` 表示本地匹配与排序，不能把它伪装成 AI 新生成的回忆，也不需要向 DeepSeek 发送整个共同时间线。完整字段见 `fuwai/ai/contracts/memory-search-response.schema.json`。

## 联调检查表

- [ ] 成员 2 能携带 `X-API-Key` 调用 ASR HTTPS 地址。
- [ ] `watch` 和 `pendant` 使用同一 ASR 路由，仅 `source` 不同。
- [ ] ASR 成功、失败和超时状态都能被成员 2 保存和展示。
- [ ] 用户确认前不会调用 `/api/moments/generate`。
- [ ] `/api/moments/generate` 返回合法 `moment.schema.json` 字段。
- [ ] 生活瞬间默认私有，只有拥有者调用 `/api/moments/{id}/share` 后才出现在 `/api/timeline`。
- [ ] `/api/timeline` 只返回 active 关系双方的已确认、已分享、未归档记录，并验证分页排序。
- [ ] 周报、月报、纪念日回顾只使用共同时间线可见记录，并能从 `source_event_ids` 返回原事件。
- [ ] 记忆检索只返回当前关系可见的记录，结果含 `event_id`、`matched_fields` 和可回看的确认转写。
- [ ] 高风险内容含 `high_risk_content_review` 时不展示或自动发送建议回复。
- [ ] 联调使用脱敏音频、测试用户和临时 API Key。
