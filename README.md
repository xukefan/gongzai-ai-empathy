# 共在 Gongzai AI Empathy

> 面向异地情侣的 AI 生活瞬间共感与保存系统：Apple Watch App + iPhone App + Tuya 实体挂件 + FastAPI 后端。

## 项目简介

“共在”希望降低异地情侣分享细小生活瞬间的表达成本。用户主动通过 Apple Watch 采集一段心率，并通过 iPhone 留下短语音；另一方通过 Apple Watch 的触觉感受对应节奏，通过实体挂件的柔和灯光看见这一频率，并可听取原声、触摸确认和回复。

交互分工统一为：**Apple Watch 负责触觉共感，实体挂件负责光影在场感。**

AI 仅用于语音转写、表达整理、标题生成和共同时间线归档，不进行情绪诊断，不替用户发送信息。

## 目标用户与边界

- 首要用户：处于异地状态、希望保持轻量日常连接的情侣；
- 适合分享“不值得专门发消息，但希望对方知道”的生活瞬间；
- 心率默认不共享，每次由本人主动发起；
- 不支持伴侣随时查询另一方实时心率；
- 不用于疾病诊断、心理治疗或关系监控。

## 核心功能

### 1. 记录这一刻

- Apple Watch 主动采集 10～15 秒心率；
- 记录平均 BPM，后续可支持逐拍间隔；
- iPhone 录制 10～30 秒原声；
- 用户确认后才创建和发送生活瞬间。

### 2. 感受这一刻

- Apple Watch 根据对方 BPM 播放系统触觉；
- 挂件不安装振动马达，通过 LED 柔和脉动呈现心跳频率；
- 建议单次光脉冲采用“快速亮起、缓慢熄灭”，避免生硬闪烁；
- 60 BPM 对应 1000 ms 间隔，80 BPM 对应 750 ms，100 BPM 对应 600 ms；
- 挂件播放对方原声；
- 灯光颜色和频率不代表固定情绪。

### 3. 回应与保存

- 挂件轻触或长按上报“已收到”或回应事件；
- iPhone / Apple Watch 展示送达、播放、确认和回复状态；
- AI 为真实片段生成可确认的标题和摘要；
- 双方记录进入共同时间线，可查看、删除和解绑。

## 系统架构

```text
Apple Watch App
├─ HealthKit：主动采集心率
├─ WatchConnectivity：与配对 iPhone 通信
└─ Haptics：重现对方心跳节奏
          │
          ▼
iPhone App
├─ 登录与情侣绑定
├─ 分享确认与短语音
├─ 共同时间线
├─ 挂件绑定
└─ 隐私与勿扰设置
          │ HTTPS / WebSocket / Push
          ▼
FastAPI 后端
├─ 用户、关系与设备管理
├─ 心跳、语音与生活片段存储
├─ 消息状态、去重与重试
├─ AI 服务编排
└─ Tuya OpenAPI / 消息订阅
          │
          ▼
Tuya 云平台
├─ 产品、PID 与物模型 DP
├─ 设备控制
└─ 设备事件上报
          │
          ▼
T5AI 实体挂件
├─ LED 灯环 / 柔光灯
├─ 触摸 / 按键
├─ 扬声器
└─ 可选麦克风
```

`WatchConnectivity` 只连接同一用户配对的 Apple Watch 与 iPhone；异地用户之间必须经过业务后端。

## 目录结构

```text
gongzai-ai-empathy/
├── apple/
│   ├── ios/
│   ├── watch/
│   └── shared/
├── pendant/
│   ├── src/
│   ├── include/
│   └── README.md
├── backend/
│   ├── app/
│   ├── tests/
│   └── .env.example
├── ai/
│   ├── prompts/
│   ├── evaluation/
│   └── README.md
├── docs/
│   ├── api/
│   ├── hardware/
│   ├── product/
│   └── testing/
└── README.md
```

## 四人分工

### 成员 1：Apple 端、挂件设备端与技术总负责（用户本人）

**Apple Watch**

- 配置 HealthKit 权限并完成短时心率采集；
- 计算平均 BPM，后续支持逐拍间隔；
- 通过 WatchConnectivity 把数据发送给 iPhone；
- 接收对方 BPM，并使用系统触觉按节奏播放；
- 展示发送、送达、回应、离线和失败状态。

**iPhone**

- 实现 WatchConnectivity 双向通信；
- 完成登录、情侣绑定、分享确认和共同时间线；
- 录制短语音并调用成员 2 提供的后端 API；
- 接收远端事件并转发给 Apple Watch；
- 根据成员 4 的 UI 稿完成 SwiftUI 页面。

**实体挂件设备端**

- 完成 T5AI、LED 灯环、触摸模块和扬声器接线；
- 使用 PWM 实现柔和光脉冲，并限制最大亮度和过快闪烁；
- 根据 heartbeat_bpm / beat_intervals 播放灯光节奏；
- 处理 Tuya DP，实现灯光、语音和触摸确认；
- 不安装振动马达；
- 负责最终端到端技术联调。

**交付物**：iOS/watchOS App、挂件原型、接线和固件说明、端到端演示。

### 成员 2：FastAPI 后端与 Tuya 云负责人

- 负责用户、情侣关系、设备绑定和权限；
- 设计心跳事件、生活片段、语音和回应数据表；
- 提供 iPhone 使用的 REST API / WebSocket；
- 生成唯一 event_id，实现去重、状态流转和失败重试；
- 创建 Tuya 产品、PID、虚拟设备和授权；
- 维护 DP：heartbeat_bpm、beat_intervals、light_pattern、brightness、play_duration、event_id、touch_event、acknowledge；
- 通过 Tuya OpenAPI 下发灯光任务；
- 通过消息订阅接收挂件触摸、确认和在线状态；
- 与成员 1 联调：成员 2 负责让数据到达设备，成员 1 负责设备本地动作。

**交付物**：FastAPI 服务、数据库、Tuya 云项目、API/DP 文档、重试与设备模拟工具。

### 成员 3：AI、语音与数据负责人

- 完成语音转文字；
- 生成忠于原意的短标题和可选摘要；
- 整理心跳、原声、时间和回应，形成共同时间线；
- 生成基于真实记录的周度回顾；
- 定义 Moment、HeartbeatEvent 和 AIResult 数据结构；
- 建立摘要忠实度、隐私和幻觉测试集；
- AI 输出必须由用户确认后才能保存或发送；
- 禁止根据心率判断具体情绪、诊断疾病或自动通知伴侣。

**交付物**：语音与 AI 服务、提示词、至少 20 条评估用例、时间线模块和 AI 安全边界。

### 成员 4：产品、UI、用户研究与质量负责人

- 明确用户需求、使用场景和不做清单；
- 设计 Watch、iPhone 和挂件交互流程；
- 输出 Watch/iPhone 高保真 UI；
- 设计挂件外观、灯光状态和可选 3D 打印外壳；
- 灯光只表示设备状态和心跳节奏，不赋予固定情绪含义；
- 组织 5～10 对异地情侣访谈和可用性测试；
- 测试灯光舒适度、误解风险、分享意愿、延迟和成功率；
- 维护 GitHub Project、Issues、测试记录、PPT、视频和答辩材料。

**交付物**：需求与交互稿、UI/外观方案、用户研究、测试报告和比赛材料。

### 跨模块责任边界

| 链路 | 主负责人 | 协作人 |
|---|---|---|
| Watch 采集心率并传给 iPhone | 成员 1 | — |
| iPhone 上传后端 | 成员 1 | 成员 2 |
| 后端保存、转发与状态管理 | 成员 2 | 成员 3 |
| 后端下发 Tuya 云 | 成员 2 | 成员 1 |
| 挂件按 BPM 灯光脉动 | 成员 1 | 成员 2 |
| 挂件触摸回传 Watch | 成员 2 | 成员 1 |
| AI 标题、摘要与时间线 | 成员 3 | 成员 2、成员 4 |
| UI、测试与答辩材料 | 成员 4 | 全员 |

核心协作原则：成员 1 与成员 2 从第一周开始联调；任何附加功能都不得阻塞“手表发送—挂件亮灯—挂件回应—手表收到”的主链路。

## 分支与提交规范

- `main` 始终保持可构建、可演示，不直接提交；
- 每个 Issue 对应一个短生命周期分支；
- 分支示例：`feature/watch-heart-rate`、`feature/pendant-light-pulse`、`feature/backend-heartbeat-api`、`feature/ai-moment-title`；
- 提交使用 `<type>(<scope>): <summary>`；
- 示例：`feat(pendant): render heartbeat pattern with light`；
- PR 必须关联 Issue、说明验证方法并由至少一名队友 Review；
- API、DP 或数据结构变化必须同步更新 `docs/api/` 和测试。

## 统一事件结构

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

状态统一为：

```text
created → uploaded → delivered → played → acknowledged → replied
                                                    └→ failed
```

## 密钥与隐私

禁止提交 Tuya Access Secret、设备授权码、AI API Key、数据库密码、Apple 私钥、`.env`、真实心率、语音、照片和关系数据。

- 心率默认不共享，每次由本人主动发起；
- AI 摘要未经确认不得发送；
- 解绑后立即停止数据互通；
- 灯光颜色、闪烁频率、手表触觉和 BPM 不作为通用情绪编码或医疗结论；
- 测试使用合成或匿名数据。

## 里程碑

| 里程碑 | 完成定义 |
|---|---|
| M1：Apple 技术验证 | Watch 真机采集心率并传给 iPhone |
| M2：挂件本地验证 | 输入 60/80/100 BPM，挂件按频率柔和脉动，触摸产生事件 |
| M3：云端控制挂件 | 后端经 Tuya 下发 BPM，挂件开始亮灯 |
| M4：端到端发送 | Watch → iPhone → Backend → Tuya → Pendant |
| M5：双向回应 | Pendant → Tuya → Backend → iPhone → Watch |
| M6：生活瞬间 | 心率、原声、灯光、送达和回应形成完整记录 |
| M7：AI 与时间线 | AI 标题可确认，时间线可查看和删除 |
| M8：比赛版本 | 弱网和掉线测试完成，PPT、文档和视频就绪 |

## 第一周任务

### 成员 1

- [ ] 建立 iOS + watchOS 工程并安装到真机；
- [ ] Watch 读取并显示心率；
- [ ] Watch 将平均 BPM 传给 iPhone；
- [ ] Watch 根据 BPM 播放触觉；
- [ ] T5AI 本地按 60/80/100 BPM 控制 LED 脉动；
- [ ] 记录 LED 接线、亮度限制和供电方式。

### 成员 2

- [ ] 创建 FastAPI 项目和健康检查接口；
- [ ] 创建 Tuya 产品、DP 和虚拟设备；
- [ ] 验证云端下发 heartbeat_bpm / light_pattern；
- [ ] 起草心跳发送接口和 `.env.example`。

### 成员 3

- [ ] 确定 Moment 与 HeartbeatEvent 字段；
- [ ] 跑通语音转文字；
- [ ] 生成不超过 20 字且忠于原意的标题；
- [ ] 建立至少 10 条首批 AI 测试用例。

### 成员 4

- [ ] 完成核心用户流程和页面线框图；
- [ ] 完成挂件灯光状态与外观草案；
- [ ] 建立 GitHub Project 和第一周 Issues；
- [ ] 建立测试模板和异地情侣访谈提纲。

## 第一周验收

1. Apple Watch 真机读取并显示真实心率；
2. iPhone 收到 Watch 发送的结构化 BPM；
3. Apple Watch 可以按测试 BPM 播放触觉；
4. T5AI 挂件可在不依赖云端时按 60/80/100 BPM 柔和脉动；
5. Tuya 虚拟设备收到云端 DP；
6. 仓库中没有密钥、真实健康数据或个人语音；
7. 四名成员对事件结构、DP 和责任边界达成一致。

## 当前不做

- 全天持续心率监测；
- 自动向伴侣推送异常状态；
- 精确识别开心、悲伤或焦虑；
- 心理疾病监测、诊断和治疗；
- 医疗级实时同步或原始 PPG 波形传输；
- 量产级电池、小型化、防水和认证；
- 完整情侣社区或通用即时通信。

## 协作底线

1. 先打通闭环，再增加功能；
2. 代码、接口和文档同步变化；
3. `main` 始终可构建、可演示；
4. 健康与关系数据必须由用户主动授权；
5. 心率是生活瞬间的情境信号，不是情绪或疾病的答案。
