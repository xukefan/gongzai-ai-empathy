# DeepSeek AI 交付目录

本目录是成员 3 的 AI 大模型交付入口。当前模型为 `deepseek-v4-flash`，调用发生在后端服务端，客户端不直接持有密钥。

## 阅读顺序

1. [`deepseek-v4-flash-integration.md`](deepseek-v4-flash-integration.md)：安装、配置、请求示例、错误处理和验收流程。
2. [`../evaluation/ai-p0-evaluation-report.md`](../evaluation/ai-p0-evaluation-report.md)：离线基线与真实模型验收要求。
3. [`../../fuwai/ai/contracts/ai-moment-request.schema.json`](../../fuwai/ai/contracts/ai-moment-request.schema.json)：请求 JSON Schema。
4. [`../../fuwai/ai/contracts/moment.schema.json`](../../fuwai/ai/contracts/moment.schema.json)：响应 JSON Schema。
5. [`../../fuwai/ai/contracts/ai-error.schema.json`](../../fuwai/ai/contracts/ai-error.schema.json)：错误 JSON Schema。
6. [`../../backend/ai_prompts.py`](../../backend/ai_prompts.py)：`moment-v1` Prompt 源码。

## Python 文件

| 文件 | 用途 |
|---|---|
| `backend/deepseek_client.py` | DeepSeek OpenAI-compatible HTTP 调用和错误分类 |
| `backend/ai_service.py` | 业务入口、输出校验、安全策略、fallback 和一次修复重试 |
| `backend/ai_prompts.py` | 版本化 Prompt 和消息构造 |
| `backend/ai_errors.py` | 稳定业务错误码 |
| `backend/ai_schemas.py` | Pydantic 请求、响应和错误模型 |
| `backend/ai_smoke_test.py` | 使用脱敏文本的单条在线 smoke test |
| `backend/evaluation/run_ai_evaluation.py` | 不调用外部模型的离线评估 |
| `backend/evaluation/live_ai_evaluation.py` | 需显式开启的 DeepSeek 在线评估 |

## 当前边界

- 讯飞 ASR 文件仍位于 `asr/` 和 `fuwai/ai/`，不由 DeepSeek 替代；
- AI 只接收用户确认后的转写文字，不接收原始音频；
- 真实 API Key 只放在服务器环境变量或密钥管理器中；
- 时间线、周报、月报、纪念日回顾和语义检索属于后续 P1/P2，不在当前单条瞬间 P0 接口内。
