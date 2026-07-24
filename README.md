# 共在 Gongzai AI Empathy

> AI 生理共感与异地情侣生活瞬间分享系统：Apple Watch App + iPhone App + Tuya 实体挂件 + FastAPI 后端。

## 项目简介

“共在”面向异地情侣，希望降低分享细小生活瞬间的表达成本。用户可以在 Apple Watch 上主动采集一小段心率，并通过 iPhone 录制短语音；系统把心跳、原声、时间和回应组合为一个“生活瞬间”。另一方可通过 Apple Watch 或实体挂件感受对应的搏动节奏、听取原声并回应。AI 只负责辅助整理表达、生成标题和归档共同时间线，不做医疗诊断，不替用户自动发送情绪或健康信息。

项目当前以比赛可演示原型为目标，优先打通可靠的双向通信闭环，再逐步增加语音、AI 和长期记忆能力。

## 目标用户

首要用户为处于异地状态、希望保持日常连接的情侣，尤其适合以下情境：

- 想分享一个细小瞬间，但觉得专门发消息过于正式或矫情；
- 想传递“我在想你”“我已经收到”，又不希望打断对方；
- 希望给语音消息补充当时真实的身体节奏与情境；
- 希望把零散的心跳、原声和回应沉淀为双方共同记忆。

本项目不面向疾病诊断、心理治疗或伴侣监控场景。

## 核心功能

### 1. 记录这一刻

- 用户主动在 Apple Watch 发起 10～15 秒心率采集；
- 记录平均 BPM，后续可增加逐拍间隔；
- 通过 iPhone 录制 10～30 秒原声；
- 用户确认后才创建并发送生活瞬间。

### 2. 感受这一刻

- 接收方 Apple Watch 按节奏播放系统触觉；
- Tuya 实体挂件通过马达重现心跳节奏；
- 挂件可播放原声，并使用灯光提示新事件；
- 灯光和震动不预设通用情绪含义。

### 3. 回应这一刻

- 挂件轻触或长按上报“已收到”或回应事件；
- iPhone / Apple Watch 展示送达、播放、确认和回复状态；
- 后续可增加短语音回复。

### 4. 记住这一刻

- AI 在不改变原意的前提下生成标题和可选摘要；
- 用户可查看原声、心跳、时间和双方回应；
- 系统按时间形成双方共同生活时间线；
- 用户可删除记录并解除绑定。

## 系统架构

```text
Apple Watch App
├─ HealthKit：主动采集心率
├─ WatchConnectivity：与配对 iPhone 通信
└─ Haptics：近似重现对方的心跳节奏
          │
          ▼
iPhone App
├─ 账号与情侣绑定
├─ 心跳分享确认
├─ 短语音录制与上传
├─ 共同时间线
├─ 挂件绑定与设置
└─ 隐私与勿扰设置
          │ HTTPS / WebSocket / Push
          ▼
FastAPI 业务后端
├─ 用户、关系和设备管理
├─ 心跳与生活瞬间存储
├─ 消息状态、去重和重试
├─ AI 服务编排
└─ Tuya OpenAPI / 消息订阅
          │
          ▼
Tuya 云平台
├─ 产品与物模型（DP）
├─ 设备控制
└─ 设备事件上报
          │
          ▼
实体挂件（T5AI 原型）
├─ 振动马达
├─ LED
├─ 触摸 / 按键
├─ 扬声器
└─ 可选麦克风
```

跨用户通信必须经过业务后端。`WatchConnectivity` 仅用于同一用户配对的 Apple Watch 与 iPhone 之间的通信。

## 目录结构

项目采用 Monorepo，所有端共用一个私有仓库：

```text
gongzai-ai-empathy/
├── apple/
│   ├── ios/                 # iPhone App
│   ├── watch/               # Apple Watch App
│   └── shared/              # Apple 端共享模型与协议
├── pendant/
│   ├── src/                 # T5AI / TuyaOpen 固件源代码
│   ├── include/
│   ├── config/
│   └── README.md            # 接线、烧录与调试说明
├── backend/
│   ├── app/                 # FastAPI 业务代码
│   ├── tests/
│   ├── requirements.txt
│   └── .env.example
├── ai/
│   ├── prompts/             # 提示词及版本记录
│   ├── evaluation/          # 摘要忠实度与安全评估
│   └── README.md
├── docs/
│   ├── api/                 # HTTP、事件及错误码协议
│   ├── hardware/            # 原理图、接线与物料清单
│   ├── product/             # 需求、交互和用户调研
│   └── testing/             # 测试计划与验收记录
├── .gitignore
└── README.md
```

目录可随项目落地调整；任何结构调整都应在 PR 中说明。

## 四人分工

| 角色 | 负责人范围 | 主要交付 |
|---|---|---|
| 成员 1：Apple 端与挂件负责人 | iPhone、watchOS、HealthKit、WatchConnectivity、挂件本地硬件控制、总体联调 | Apple 端 App、挂件原型、端到端演示 |
| 成员 2：后端与 Tuya 云负责人 | FastAPI、数据库、情侣绑定、Tuya 产品与 DP、OpenAPI、设备消息订阅 | 后端服务、Tuya 云项目、设备通信接口 |
| 成员 3：AI 与数据负责人 | 语音转写、标题与摘要、共同时间线、个人状态偏离分析原型、AI 评估 | AI 服务、提示词、评估结果、数据处理模块 |
| 成员 4：产品与质量负责人 | 需求、UI/UX、用户调研、测试管理、README、PPT、视频和答辩材料 | 产品稿、测试报告、演示与比赛材料 |

协作原则：成员 1 与成员 2 从第一周开始共同联调；AI 和展示功能不得阻塞“手表到挂件再回传”的核心链路。

## 分支规范

- `main`：始终保持可构建、可演示，不直接提交。
- 每个 Issue 对应一个短生命周期分支。
- 推荐格式：`类型/模块-简短任务`。

示例：

```text
feature/watch-heart-rate
feature/ios-watch-connectivity
feature/pendant-heartbeat
feature/backend-heartbeat-api
feature/tuya-dp
feature/ai-moment-title
fix/ios-offline-retry
docs/api-event-schema
```

分支类型：

- `feature/`：新增功能；
- `fix/`：缺陷修复；
- `docs/`：文档变更；
- `refactor/`：不改变外部行为的重构；
- `test/`：测试代码或测试数据；
- `chore/`：构建、依赖和仓库维护。

## 提交规范

采用 Conventional Commits 的简化形式：

```text
<type>(<scope>): <summary>
```

示例：

```text
feat(watch): add HealthKit heart rate collection
feat(pendant): play heartbeat pattern with motor
feat(backend): add heartbeat event endpoint
fix(ios): cache events when Watch is unreachable
docs(api): update heartbeat packet fields
test(ai): add summary fidelity cases
```

要求：

- 一次提交只解决一类问题；
- 摘要使用祈使语气，简洁说明“做了什么”；
- 不提交无法编译的大范围半成品；
- 不在提交信息中写密钥、个人信息或真实健康数据；
- 合并前整理明显的调试提交，如 `test`、`try again`、`临时修改`。

## Issue 与 PR 规范

### Issue

每个任务应创建 Issue，并至少包含：

- 背景与目标；
- 负责人；
- 输入与输出；
- 依赖任务；
- 验收步骤；
- 截止时间；
- 风险或未决问题。

Issue 标题示例：

```text
[Watch] 完成短时心率采集
[Pendant] 根据 BPM 驱动马达
[Backend] 新增心跳事件接口
[AI] 生成生活片段标题
```

### Pull Request

- 禁止直接向 `main` 推送；
- PR 必须关联 Issue，例如 `Closes #12`；
- PR 说明必须包含：改动内容、验证方法、界面或硬件证据、影响范围；
- 至少一名非作者成员完成 Review；
- Apple、后端或固件无法自动验证时，应附真机截图、日志或演示视频；
- 合并前必须解决阻塞性评论，并保证相关文档同步更新；
- 默认使用 Squash merge，保持主分支历史清晰。

推荐 PR 模板：

```markdown
## 改动内容

## 关联 Issue
Closes #

## 验证方法

## 截图 / 日志 / 硬件演示

## 接口、DP 或隐私影响

## 检查清单
- [ ] 本地构建或测试通过
- [ ] 未提交密钥和真实用户数据
- [ ] 已更新相关文档
- [ ] 已考虑失败与离线状态
```

## 接口变更规范

Apple 端、后端、AI 和挂件通过统一事件模型协作。第一版建议使用：

```json
{
  "event_id": "uuid",
  "sender_id": "user_a",
  "receiver_id": "user_b",
  "average_bpm": 82,
  "beat_intervals_ms": [730, 745, 720],
  "recorded_at": "2026-07-28T15:30:00+08:00",
  "voice_url": null,
  "title": null,
  "status": "created",
  "schema_version": 1
}
```

事件状态统一为：

```text
created → uploaded → delivered → played → acknowledged → replied
                                                    └→ failed
```

变更规则：

1. API、事件字段、DP 名称或数据类型不得只在代码中修改；
2. 变更前创建 Issue，并标注影响的端；
3. 同一个 PR 中更新 `docs/api/`、示例载荷与相关测试；
4. 删除字段、重命名字段或改变语义属于破坏性变更，必须提升 `schema_version`；
5. 新字段优先设计为接收端可忽略的可选字段；
6. PR 描述中列出兼容策略、迁移方式和联调负责人；
7. Tuya DP 变更必须同步更新 DP 表、固件映射和后端下发逻辑。

## 密钥与隐私规则

### 禁止提交

- Tuya Access ID、Access Secret 和设备授权码；
- 大模型 API Key；
- 数据库密码和正式环境 URL；
- Apple 证书、私钥、Provisioning Profile；
- `.env`、`Secrets.xcconfig`、`local_config.h`；
- 真实用户的心率、语音、照片、关系信息；
- 包含个人信息的测试日志和数据库备份。

仓库仅提供无值模板：

```env
TUYA_ACCESS_ID=
TUYA_ACCESS_SECRET=
DATABASE_URL=
AI_API_KEY=
```

若密钥曾进入 Git 历史，不能只删除文件：应立即废止旧密钥并重新生成，再清理历史。

### 产品隐私边界

- 心率默认不共享，每次由本人主动发起；
- 接收方不能随时查询另一方的实时心率；
- AI 不根据单次心率直接判断焦虑、悲伤或疾病；
- AI 摘要未经用户确认不得发送；
- 用户可删除个人记录并解除关系绑定；
- 解绑后应立即停止数据互通；
- 灯光、震动和 BPM 不被宣传为通用情绪编码或医疗结论；
- 测试使用合成或匿名数据，正式用户数据不得写入仓库。

## 开发环境

### Apple 端

- macOS；
- 当前稳定版 Xcode；
- Swift / SwiftUI；
- iOS App 与配套 watchOS App；
- HealthKit；
- WatchConnectivity；
- 真实 iPhone 与配对 Apple Watch，用于心率、触觉和连接测试。

### 挂件端

- T5AI 开发板；
- TuyaOpen C SDK；
- 振动马达及 MOSFET / 专用驱动；
- LED、触摸模块、扬声器；
- USB 供电作为比赛原型默认方案；
- 涂鸦开发者平台产品、PID、授权与 DP 配置。

### 后端与 AI

- Python 3.11 或团队统一版本；
- FastAPI；
- SQLite（原型）或 PostgreSQL（联调/部署）；
- 对象存储用于语音文件；
- Tuya OpenAPI 与设备消息订阅；
- 大模型 / 语音转写服务；
- 使用 `.env.example` 说明配置项，真实值仅保存在本地或受控 Secrets 中。

## 里程碑

| 里程碑 | 目标 | 完成定义 |
|---|---|---|
| M1：Apple 技术验证 | 手表采集并传出心率 | 真机显示 BPM，10～15 秒采集后传到配对 iPhone |
| M2：挂件本地验证 | 马达和触摸可控 | 输入 BPM 后按节奏振动，触摸产生本地事件 |
| M3：云端控制挂件 | Tuya 链路可用 | 后端或云端下发 BPM，挂件开始振动 |
| M4：端到端发送 | 手表控制异地挂件 | Watch → iPhone → Backend → Tuya → Pendant 稳定运行 |
| M5：双向回应 | 挂件回应回到手表 | Pendant → Tuya → Backend → iPhone → Watch 完成确认 |
| M6：生活瞬间 | 加入语音和状态 | 心跳、原声、送达和回应形成一条完整记录 |
| M7：AI 与时间线 | 整理真实内容 | AI 标题可确认，双方时间线可查看和删除 |
| M8：比赛版本 | 稳定演示与材料 | 弱网/掉线测试完成，演示视频、PPT 和文档就绪 |

建议在各里程碑完成后创建 Git Tag：

```text
v0.1-watch-heart-rate
v0.2-pendant-local-demo
v0.3-watch-to-pendant
v0.4-two-way-response
v0.5-moment-and-ai
v1.0-competition-demo
```

## 第一周任务

### 成员 1：Apple 端与挂件

- [ ] 建立 iOS + watchOS 同一 Xcode 工程；
- [ ] 两个 Target 完成签名并安装到真机；
- [ ] HealthKit 请求心率读取权限；
- [ ] Watch 显示实时或短时采集 BPM；
- [ ] Watch 将平均 BPM 传给 iPhone；
- [ ] T5AI 本地驱动马达，分别演示 60、80、100 BPM；
- [ ] 记录马达接线、驱动和供电方式。

### 成员 2：后端与 Tuya 云

- [ ] 创建 FastAPI 空项目和健康检查接口；
- [ ] 创建 Tuya 产品与虚拟设备；
- [ ] 定义第一版 DP；
- [ ] 验证云端下发 `heartbeat_bpm`；
- [ ] 起草 `POST /api/heartbeat/send` 接口；
- [ ] 提交 `.env.example`，确认密钥不进入仓库。

### 成员 3：AI 与数据

- [ ] 确定 Moment 和 HeartbeatEvent 数据字段；
- [ ] 跑通一条语音转文字流程；
- [ ] 生成不超过 20 字、忠于原意的生活片段标题；
- [ ] 建立至少 10 条摘要忠实度测试用例；
- [ ] 写明 AI 禁止执行的行为与输出边界。

### 成员 4：产品与质量

- [ ] 完成核心用户流程和页面线框图；
- [ ] 形成第一版需求边界和“不做清单”；
- [ ] 建立 GitHub Project：待处理、开发中、待测试、已完成；
- [ ] 把第一周任务拆成 Issues；
- [ ] 建立测试记录模板；
- [ ] 设计 5～10 对异地情侣的访谈提纲。

## 验收标准

### 第一周验收

必须现场或通过视频证明：

1. Apple Watch 真机可读取并显示真实心率；
2. 采集结束后，iPhone 可收到结构化 BPM 数据；
3. T5AI 挂件可在不依赖云端的情况下按 60、80、100 BPM 振动；
4. Tuya 虚拟设备能收到云端下发的 `heartbeat_bpm`；
5. 仓库没有密钥、真实健康数据或个人语音；
6. 核心事件结构在 Apple、后端、AI 和挂件成员之间达成一致。

### 比赛最小版本验收

- 用户主动在 Apple Watch 采集一段真实心率；
- 数据经过 iPhone、后端与 Tuya 云到达挂件；
- 挂件在正常网络下于合理时间内开始重现节奏；
- 挂件触摸确认能够回传到发送方 Apple Watch；
- 每个事件具有唯一 `event_id`，重复请求不会生成多次播放；
- 挂件离线、网络失败或权限被拒绝时，用户能看到明确状态；
- 心率、语音和 AI 标题只有在用户确认后才发送；
- AI 不生成医疗结论，不虚构用户未表达的感受；
- 共同时间线支持查看、删除和解绑后的访问终止；
- `main` 分支对应版本可以按照仓库文档重新构建并完成演示。

## 当前范围与不做清单

为了优先完成可靠原型，第一版暂不实现：

- 全天持续心率监测；
- 自动向伴侣推送异常生理状态；
- 精确识别开心、悲伤、焦虑等具体情绪；
- 心理疾病监测、诊断或治疗；
- 医疗级实时同步或原始 PPG 波形传输；
- 量产级电池、小型化、防水和认证；
- 完整情侣社区或通用即时通信功能。

## 协作底线

1. 先打通闭环，再增加功能；
2. 代码、接口和文档同步变化；
3. `main` 始终可构建、可演示；
4. 任何健康与关系数据都以用户主动授权为前提；
5. 心率是生活瞬间的情境信号，不是情绪或疾病的答案。
