# DeepSeek v4 Flash AI 集成说明

本文是成员 3 给成员 1、成员 2 的完整 AI 交付说明。讯飞 ASR 与本文是两个独立供应商：讯飞负责音频转写，DeepSeek 负责确认文字的整理。

## 1. 责任边界

```text
Apple Watch / 挂件录音
  -> 讯飞录音文件转写大模型（ASR）
  -> 用户查看并确认 transcript
  -> POST /api/moments/generate
  -> DeepSeek v4 Flash
  -> 结构化生活瞬间 JSON
```

成员 3 负责 Prompt、DeepSeek 适配、输出校验、安全规则、评估和契约；成员 2 负责鉴权、数据库、任务状态、重试调度和结果持久化；成员 1 负责客户端确认界面和展示。

## 2. DeepSeek 配置

官方 OpenAI-compatible API 的配置形式如下，Base URL 和模型 ID 以负责人账号控制台为准：

```env
AI_API_BASE_URL=https://api.deepseek.com
AI_API_KEY=在服务器环境变量中填写，不提交仓库
AI_MODEL=deepseek-v4-flash
AI_TIMEOUT_SECONDS=30
AI_PROMPT_VERSION=moment-v5
```

项目适配器会向 `${AI_API_BASE_URL}/chat/completions` 发起 POST 请求，使用 `Authorization: Bearer <key>`。客户端和 GitHub 不接触 API Key。

如果负责人是在第三方平台开通 DeepSeek 模型，必须把该平台的 Base URL、鉴权方式和实际模型 ID 发给成员 3；不要仅凭“v4flash”简称修改生产配置。

## 3. 本地安装与配置

```powershell
cd D:\竞赛\服外\应用赛\2026年\code\gongzai-ai-empathy\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

在 `.env` 中填写 `AI_API_KEY`。`.env` 已被 `.gitignore` 忽略，禁止把内容粘贴到 Issue、聊天或提交记录。

## 4. 调用接口

### 请求

```http
POST /api/moments/generate
Content-Type: application/json
```

```json
{
  "user_id": "demo-user",
  "content": "今天答辩终于结束了，虽然有点乱，但现在松了一口气。",
  "voice_id": "voice-001",
  "bpm": 82
}
```

`content` 必须是用户确认后的转写文字。原始录音不能放入 Prompt。当前路由的认证和 consent 校验由成员 2 的网关负责。

### 成功响应中的 data

```json
{
  "id": "moment-001",
  "user_id": "demo-user",
  "title": "答辩结束后的记录",
  "summary": "今天答辩有些混乱，但结束后松了一口气。",
  "raw_text": "今天答辩终于结束了，虽然有点乱，但现在松了一口气。",
  "voice_id": "voice-001",
  "ai_status": "generated",
  "tags": ["学习", "答辩"],
  "suggested_replies": ["辛苦了，结束了就好。"],
  "safety_flags": [],
  "schema_version": 1,
  "prompt_version": "moment-v5"
}
```

`raw_text` 是原始确认转写，`summary` 是 AI 摘要，两者不能互相覆盖。回复建议必须经过用户主动选择后才能发送。

`suggested_replies` 是可选的回复草稿，不是自动发送指令。模型最多返回 3 条，服务端会去空、去重并将每条限制为 200 个字符。草稿只能基于确认转写中明确出现的内容，使用尊重、非强迫的可能性表达，不得虚构关系或承诺，不得加入诊断/医疗/法律建议。遇到自伤、他伤、急性身体不适或无法形成合适回应的内容时，服务端强制返回空数组，并通过 `safety_flags` 交给上层安全流程处理。

## 5. DeepSeek 请求格式

适配器发送的核心字段：

```json
{
  "model": "deepseek-v4-flash",
  "temperature": 0.3,
  "response_format": {"type": "json_object"},
  "messages": [
    {"role": "system", "content": "见 backend/ai_prompts.py"},
    {"role": "user", "content": "确认后的转写文字"}
  ]
}
```

如果负责人所用平台不支持 `response_format=json_object`，需要提供平台错误响应，由成员 3 增加兼容分支；不能在客户端绕过服务端直接调用模型。

## 6. 失败处理

| 场景 | 处理 |
|---|---|
| 未配置 Key | 本地返回 `fallback`，线上部署应配置 Key |
| 408/超时 | 返回 `AI_TIMEOUT`，保留原文，可重试 |
| 429/5xx | 返回 `AI_PROVIDER_UNAVAILABLE`，按退避策略重试 |
| 401/403 | 返回 `AI_PROVIDER_AUTH_FAILED`，检查 Key 和账户权限，不要重试风暴 |
| 400/404 | 返回 `AI_INVALID_REQUEST`，检查 Base URL、模型 ID 和 JSON 模式 |
| 返回结构缺失 | 返回 `AI_INVALID_RESPONSE`，不展示生成成功 |
| JSON 字段或类型不合法 | 自动修复请求一次，仍失败返回 `AI_OUTPUT_SCHEMA_INVALID` |
| 高风险原文 | 强制加入 `high_risk_content_review`，清空回复建议 |

API 错误结构见 `fuwai/ai/contracts/ai-error.schema.json`。

## 7. 安全规则

- 不根据 BPM 推断情绪或疾病；
- 不补写原文不存在的人、事、时间、地点；
- 不评价情侣关系；
- 不自动发送回复或通知伴侣；
- 不在日志记录 API Key、录音 URL、完整转写或健康数据；
- 高风险文字只标记并交给产品流程提示，不输出诊断结论。

## 8. 文件清单

- `backend/ai_service.py`：业务入口、JSON 校验、安全策略和 fallback；
- `backend/deepseek_client.py`：DeepSeek HTTP 适配器；
- `backend/ai_prompts.py`：`moment-v5` 版本 Prompt；
- `backend/ai_errors.py`：稳定错误码异常；
- `backend/ai_schemas.py`：Pydantic 输入、输出、错误模型；
- `backend/ai_service.py`：被 `/api/moments/generate` 调用；
- `backend/evaluation/`：10 条脱敏离线评估用例和脚本；
- `backend/tests/`：AI 单元与契约测试；
- `fuwai/ai/contracts/`：JSON Schema；
- `docs/ai/`：供应商、部署和联调文档。

## 9. 验收命令

```powershell
cd D:\竞赛\服外\应用赛\2026年\code\gongzai-ai-empathy\backend
python -m unittest discover -s tests -v
python evaluation\run_ai_evaluation.py
python ai_smoke_test.py --text "今天完成了一个脱敏测试记录。"
```

前两条不调用线上模型，必须分别得到 `9/9` 和 `10/10`。最后一条只有在服务器或本地 `.env` 配置真实 Key 后才执行。
