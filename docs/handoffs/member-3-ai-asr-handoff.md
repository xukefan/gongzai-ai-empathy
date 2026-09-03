# 任务三交接文档：服务端 ASR 与 AI 生活记录

> 本文用于把“成员 3：AI 与数据处理”交给新的负责人。请先阅读本文，再阅读仓库根目录的 `README.md`、`docs/architecture/technical-route.md` 和 `docs/reviews/xwr-666-backend-review.md`。

## 0. 一页结论

任务三的目标不是做一个情绪诊断器，而是完成下面这条链路：

```text
Apple Watch / T5AI 挂件录音
→ 服务器统一语音转文字（ASR）
→ 用户确认转写内容
→ AI 生成标题、摘要、标签和可选回复建议
→ 成员 2 保存为生活瞬间
→ AI 按真实记录生成共同时间线、周报和回忆
```

当前产品场景是异地情侣。最终形态是双方都可以使用 Apple Watch、iPhone App 和实体挂件；比赛原型先用一组 Watch/iPhone 加一个挂件验证非对称闭环。

**当前已经存在的基础**：仓库已有 `backend/ai_service.py`、`/api/moments/generate` 和语音文件上传接口。

**当前仍需要完成的重点**：服务端 ASR、统一转写结果、扩展结构化 AI 输出、AI 评估集和与成员 2 的稳定集成。

当前交接基线：`main` 分支，提交 `5dfd835`。

---

## 1. 产品和技术边界

### 1.1 终端分工

| 终端 | 主要工作 |
|---|---|
| Apple Watch | 主动采集心率、录制或接收原声、展示转写文字、用系统触觉表现心率 |
| iPhone App | 接收 Watch 数据、上传原声、展示并确认转写、查看时间线 |
| T5AI 挂件 | 播放发送者原声、用 LED 表现心率节奏、按钮触发回复录音 |
| FastAPI 后端 | 音频存储、服务端 ASR、AI 调用、权限、状态、数据库和 Tuya 联动 |
| 任务三模块 | ASR 适配器、AI 工作流、提示词、结构化输出、评估和集成说明 |

### 1.2 必须遵守的产品原则

1. 所有端的录音统一上传服务器转写；不再使用外挂 ASR 模块，也不把端侧转写作为主路线。
2. 原始语音必须保存为日记和回忆资产；转写文字作为 Watch 展示、AI 输入和检索内容。
3. 原声和转写不能互相替代：挂件播放原声，Watch 主要展示转写文字。
4. 心率只作为真实身体状态背景，不能据此判断“悲伤、紧张、兴奋”等具体情绪。
5. AI 不能诊断疾病、评价关系、编造共同记忆或未经确认自动发送消息。
6. AI 结果必须经过用户确认才能进入共享时间线或发送给伴侣。

---

## 2. 任务三负责什么

### 2.1 必须交付

#### A. 服务端 ASR

- 设计统一的 ASR 服务接口；
- 接收来自 Apple Watch 和挂件的音频资产引用；
- 调用团队选定的中文语音识别服务；
- 返回原始转写、语言、状态和可选置信度；
- 处理空文件、格式不支持、超时、限流和服务不可用；
- ASR 失败时不删除原声，也不阻止用户保留原声，支持重试；
- 不在日志中输出原声内容、健康数据或 API Key。

#### B. AI 生活记录

- 根据用户确认后的转写文字生成忠实的标题、摘要和标签；
- 生成可选的、不过度解读的回复建议；
- 根据真实生活片段整理共同时间线；
- 生成周报、月报和纪念日回顾；
- 支持按时间、关键词和标签检索真实记录；
- 输出稳定 JSON，并提供 `schema_version`；
- 保留当前 `/api/moments/generate` 的 `title`、`summary`、`ai_status` 兼容字段。

#### C. 评估和集成

- 建立脱敏测试集，不使用真实情侣的原声或健康数据；
- 对忠实度、事实幻觉、隐私泄露和不当建议进行测试；
- 提供成员 2 可以直接调用的函数接口和字段说明；
- 提供最小可运行的本地测试脚本和失败示例。

### 2.2 明确不负责

- 不负责数据库表、迁移、备份和删除策略；这些由成员 2 负责。
- 不负责 FastAPI 认证、情侣关系授权、对象存储和 API 路由最终实现；与成员 2 协作即可。
- 不负责 Apple Watch、iPhone、T5AI 固件或 Tuya DP；这些由成员 1/2 负责。
- 不根据 BPM、HRV 或一次录音诊断心理或身体疾病。
- 不自动向伴侣发送内容，不替用户决定是否分享。
- 不把真实语音、转写文字、健康数据或密钥提交到 GitHub。

---

## 3. 当前仓库状态

### 3.1 已有代码

| 文件/接口 | 当前状态 | 接手注意 |
|---|---|---|
| `backend/ai_service.py` | 已有 OpenAI-compatible Chat Completions 适配器；无 Key 时返回 `fallback` | 目前只生成 `title`、`summary`、`ai_status`，需要扩展但不能破坏旧字段 |
| `backend/main.py` `/api/voice/upload` | 已能保存上传音频并返回 `voice_id` | 当前只上传，不代表已经完成 ASR |
| `backend/main.py` `/api/moments/generate` | 已根据用户提交的 `content` 生成并保存日记 | 当前 `content` 由调用方提供，服务端 ASR 尚未接入 |
| `backend/models.py` | 已有 `VoiceRecord`、`Moment` 等基础模型 | 数据库仍由成员 2 维护，新增字段必须先和成员 2 讨论 |
| `apple/Sources/GongzaiCore/APIContract.swift` | 已有日记、语音上传和响应模型 | 新字段尽量做成可选，避免旧版 App 解码失败 |
| `docs/architecture/technical-route.md` | 已规定“所有端录音统一由服务器转写” | 以该文档为产品边界基准 |

### 3.2 当前缺口

1. 没有真正的服务端 ASR endpoint 和 provider adapter。
2. `VoiceRecord` 没有统一的转写状态、错误码和完成时间字段。
3. `Moment` 的 AI 输出目前只有标题和摘要，缺少标签、回复建议、风险标记和版本号。
4. `/api/moments/generate` 还缺少认证、关系授权和幂等保护；不要在任务三分支中自行重写数据库逻辑。
5. 现有服务器 `http://124.221.238.246:8000` 仅用于测试，上传真实语音前必须确认 HTTPS、权限和隐私策略。

---

## 4. 与成员 2 的协作契约

### 4.1 责任边界

```text
成员 3：提供纯 AI/ASR 服务函数、输入输出模型、错误码、提示词和评估
成员 2：提供认证、音频存储、数据库字段、FastAPI 路由、任务调度和持久化
```

任务三的服务函数尽量做到：

- 输入是明确的 Python 字典或 Pydantic 模型；
- 输出是可序列化的 Python 字典或 Pydantic 模型；
- 不在 service 层直接 `db.commit()`；
- 不依赖 FastAPI 的全局请求对象；
- 不在 service 层读取 `.env` 以外的个人配置；
- Provider 失败时抛出稳定、可识别的业务异常。

### 4.2 建议的 ASR 接口

最终路由由成员 2 落地，任务三先实现服务函数并提供联调示例。建议接口：

```text
POST /api/voice/{voice_id}/transcribe
```

请求参数：

```json
{
  "user_id": "user-a",
  "language": "zh-CN",
  "force": false,
  "schema_version": 1
}
```

成功响应：

```json
{
  "voice_id": "voice-001",
  "status": "completed",
  "transcript": "今天答辩终于结束了。",
  "language": "zh-CN",
  "confidence": null,
  "error_code": null,
  "schema_version": 1
}
```

失败响应：

```json
{
  "voice_id": "voice-001",
  "status": "failed",
  "transcript": null,
  "language": "zh-CN",
  "confidence": null,
  "error_code": "ASR_PROVIDER_UNAVAILABLE",
  "schema_version": 1
}
```

建议错误码：

```text
ASR_EMPTY_AUDIO
ASR_UNSUPPORTED_FORMAT
ASR_TOO_LONG
ASR_PROVIDER_UNAVAILABLE
ASR_TIMEOUT
ASR_INVALID_RESPONSE
```

### 4.3 建议的 AI 日记输入输出

输入：

```json
{
  "user_id": "user-a",
  "content": "今天答辩终于结束了，虽然有点乱，但现在松了一口气。",
  "voice_id": "voice-001",
  "bpm": 82,
  "recorded_at": "2026-09-03T15:30:00+08:00",
  "schema_version": 1
}
```

输出：

```json
{
  "title": "答辩结束后的松一口气",
  "summary": "今天答辩有些混乱，但结束后轻松了很多。",
  "tags": ["学习", "答辩", "生活片段"],
  "suggested_replies": [
    "辛苦了，结束了就好。",
    "晚上有空的话，我们聊一会儿。"
  ],
  "safety_flags": [],
  "ai_status": "generated",
  "schema_version": 1
}
```

约束：

- `summary` 只能压缩用户原意，不能补写未提供的事实；
- `bpm` 只能作为背景，不得出现在“你正在焦虑”等诊断性结论中；
- 回复建议必须是可选项，不能自动发送；
- 无 AI Key 时可以返回 `ai_status=fallback`，便于联调；
- 新增字段优先设为可选，旧客户端仍能读取标题和摘要。

---

## 5. AI 功能分层和开发优先级

### P0：必须先完成

1. 服务器端 ASR：上传音频 → 转写结果。
2. 语音转写结果供用户确认。
3. 生成标题、摘要和标签。
4. 原声、转写和 AI 结果关联到同一个 `voice_id`/`moment_id`。
5. 失败重试、fallback 和结构化 JSON。

### P1：比赛展示建议完成

1. 生成两到三条可选回复建议。
2. 共同时间线摘要。
3. 周报或月报。
4. 关键词、时间和标签检索。
5. 语音原声与文字转写并列查看。

### P2：有余力再做

1. 纪念日自动回顾真实片段。
2. 根据用户主动选择的语气生成回复草稿。
3. 同一事件的多段语音整理。
4. 用户确认后的个性化标签和摘要风格。
5. 片段去重、相似回忆聚类和时间线可视化。

不要为了“功能丰富”同时开发所有 P2 项。先把 P0 的端到端链路做稳定。

---

## 6. 推荐实现方式

### 6.1 Provider 抽象

不要把具体厂商 SDK 写死在业务逻辑里，建议分成：

```text
ai/
├── asr_service.py       # 统一 ASR 接口
├── asr_provider.py      # 具体厂商/HTTP 适配器
├── diary_service.py     # 标题、摘要、标签和回复建议
├── timeline_service.py  # 时间线、周报、回顾
├── schemas.py           # 输入输出模型
├── prompts/
└── evaluation/
```

如果暂时不新增 `ai/` 目录，也可以先在 `backend/ai_service.py` 中扩展，但请保持“provider、业务提示词、输出校验”分层。

### 6.2 配置项

建议由部署人员在服务器环境变量中配置，仓库只提交 `.env.example`：

```text
ASR_API_BASE_URL=
ASR_API_KEY=
ASR_MODEL=
ASR_TIMEOUT_SECONDS=30
AI_API_BASE_URL=https://api.openai.com/v1
AI_API_KEY=
AI_MODEL=gpt-4o-mini
AI_TIMEOUT_SECONDS=30
```

不得把真实密钥写入代码、提交记录、测试样例或 Issue。

### 6.3 音频处理原则

- 音频由成员 2 的私有存储层保存，任务三只通过授权的资产引用读取；
- 不把音频二进制塞进 DP 或 AI prompt；
- 不在普通日志打印音频 URL、原声或转写全文；
- 失败时保留原声资产，标记 `transcription_status=failed`，供重试；
- 明确区分“原始转写”和“AI 摘要”，不能用摘要覆盖原始内容。

---

## 7. 提示词和安全规则

### 7.1 日记提示词最小要求

系统提示词必须明确：

- 只使用用户提供的内容；
- 不补写人物、地点、时间和事件；
- 不进行心理、医疗或关系诊断；
- 输出合法 JSON；
- 标题简短，摘要忠于原意；
- 心率只能作为背景，不能推断具体情绪。

### 7.2 高风险内容

若文本出现自伤、他伤、急性身体不适等高风险内容：

- 不生成轻率或玩笑式回复建议；
- 返回 `safety_flags`，交给成员 2 的产品流程决定是否提示人工帮助；
- 不自动联系伴侣、家人或机构；
- 不把模型输出描述为专业诊断。

### 7.3 质量失败也要可见

AI 返回无法解析、字段缺失或疑似编造时：

```text
记录原声和原始转写
→ 标记 AI 失败
→ 返回可重试状态
→ 不显示“已生成成功”
```

---

## 8. 第一周接手计划

### 第 1 天：熟悉基线

- 克隆并运行仓库；
- 阅读根 README、技术路线和后端审查；
- 运行 `/api/health`；
- 阅读 `backend/ai_service.py` 和 `/api/moments/generate`；
- 与成员 2 确认 ASR 厂商、音频格式、最大时长、同步/异步方式。

### 第 2 天：ASR 最小闭环

- 实现 provider 无关的 `transcribe_audio()` 接口；
- 用一段脱敏中文样例音频完成上传、识别和 JSON 返回；
- 覆盖空文件、格式错误、超时和 provider 错误；
- 不修改数据库表，先用内存对象或 mock 验证。

### 第 3 天：接入后端

- 和成员 2 对齐 `voice_id`、转写状态和错误码；
- 把 ASR 结果交给成员 2 的路由和持久化流程；
- 完成“上传 → 转写 → 查询状态”的接口联调。

### 第 4 天：扩展 AI 输出

- 保留现有标题/摘要字段；
- 增加标签、回复建议、安全标记和 `schema_version`；
- 给出 fallback 结果；
- 对 malformed JSON 做校验和重试/失败处理。

### 第 5 天：评估和演示

- 准备至少 10 条脱敏测试用例；
- 完成忠实度、幻觉、隐私和心率误判测试；
- 形成一条可演示链路：

```text
样例音频
→ 服务端转写
→ 用户确认文字
→ AI 日记 JSON
→ 时间线展示数据
```

---

## 9. 验收标准

### 必过标准

- [ ] Apple Watch 和挂件音频都能走同一个服务端 ASR 接口；
- [ ] ASR 成功和失败状态可查询，错误码稳定；
- [ ] ASR 失败不会删除原声或伪造成功；
- [ ] AI 能输出合法 JSON，至少包含 `title`、`summary`、`ai_status`、`schema_version`；
- [ ] 原始转写和 AI 摘要分开保存；
- [ ] 心率不会被用于具体情绪或疾病判断；
- [ ] AI 不自动发送消息、不编造事实；
- [ ] 无 Key 时 fallback 可以支持端到端联调；
- [ ] 测试集和代码中没有真实语音、健康数据和密钥；
- [ ] 成员 2 可以按文档完成 API 接入。

### 比赛演示标准

```text
上传一段语音
→ 返回中文转写
→ 用户确认
→ 生成标题/摘要/标签
→ 保存原声关联
→ 输出一条共同生活时间线记录
```

建议额外展示一次 ASR 或 AI 服务失败，让评委看到系统会保留原声、提示重试，而不是假装成功。

---

## 10. Git 协作要求

建议分支：

```text
feature/member3-asr-ai
```

提交示例：

```text
feat(ai): add structured diary output
feat(asr): add server transcription adapter
test(ai): add hallucination and safety cases
docs(ai): document provider contract
```

提交 PR 前必须：

1. 更新接口或配置说明；
2. 提供本地运行方式；
3. 提供测试结果；
4. 说明是否新增环境变量；
5. 检查没有 `.env`、音频、健康数据、密钥和构建产物。

数据库字段、路由、状态枚举或事件结构发生变化时，先在 PR 中 @成员 2，不要单方面修改并要求其他端追赶。

---

## 11. 交接完成清单

新负责人接手后，在本文件底部补充以下信息：

```text
- 接手人：
- 接手日期：
- 当前分支：
- ASR 厂商/模型：
- AI 厂商/模型：
- 已跑通的接口：
- 未解决问题：
- 下一次联调时间：
```

任务三完成的判断标准不是“模型能聊天”，而是：

> **原声能被安全保存，服务器能统一转写，AI 能忠实整理，结果能被成员 2 持久化，并最终进入异地情侣的共同生活记录。**
