# Apple 端开发说明

本目录对应成员 1 负责的 iPhone 与 Apple Watch 原型。当前交付先完成：

1. Apple Watch 主动采集一段心率；
2. Watch 将心率片段和原声文件传给配对的 iPhone；
3. iPhone 通过临时适配层调用当前后端接口；
4. 接收端 Watch 按 BPM 使用系统触觉重现心跳节奏。

手表负责震动；挂件不包含振动马达，只用 LED 呈现心跳频率并播放原声。

## 当前联调服务器

比赛测试环境暂时使用：

```text
http://124.221.238.246:8000
```

健康检查为 `GET /api/health`。iPhone App 首次运行默认使用该地址，并会把旧版本保存的 `http://127.0.0.1:8000` 自动迁移到公网地址。

该服务器目前只有 IP 和明文 HTTP，因此测试版临时启用了针对该 IP 的 ATS 明文网络例外。心率与原声属于敏感数据，正式测试或发布前必须改用带有效证书的 HTTPS 域名，并移除这些临时例外。

## 目录

```text
apple/
├── Sources/GongzaiCore/    # 两端共享的数据模型、计算和接口适配
├── Tests/                  # 与 Apple 平台无关的单元测试
├── ios/                    # iPhone App 文件
└── watch/                  # Apple Watch App 文件
```

## 生成与打开 Xcode 工程

工程由 `project.yml` 统一生成，避免四人协作时手工配置发生漂移：

```bash
brew install xcodegen
cd apple
xcodegen generate
open Gongzai.xcodeproj
```

仓库提交 `project.yml` 和生成的共享工程，但不提交个人签名信息和
`xcuserdata`。第一次运行时，在 Xcode 的 `Signing & Capabilities` 中为
iPhone、Watch 两个 target 选择自己的 Team。

已配置：

1. iPhone App 和配套 Watch App；
2. 两端共享的本地 `GongzaiCore` package；
3. Watch HealthKit entitlement；
4. 心率读取、麦克风和 iOS 本地网络用途说明；
5. iPhone 内仅 Debug 构建可见的 60/80/100 BPM 测试入口。

Watch App 已作为 Companion App 嵌入 iPhone App。运行 `GongzaiIOS`
Scheme 时，Xcode 会构建 iPhone App 及其配套 Watch App，并通过已配对的
iPhone 尝试安装到 Apple Watch。`GongzaiWatch` Scheme 仍保留，供手表
被 Xcode 识别后单独调试 HealthKit、录音、触觉和 WatchConnectivity。

真机安装前，需要在 Xcode 中为 iPhone、Watch 两个 Target 选择同一个
开发团队，并确认两者的 Bundle Identifier 保持配套关系：

```text
iPhone: io.github.xukefan.gongzai
Watch:  io.github.xukefan.gongzai.watchkitapp
```

建议用途说明：

```text
NSHealthShareUsageDescription:
仅在用户主动分享时读取心率，用于生成心跳节奏。

NSMicrophoneUsageDescription:
仅在用户主动录制时保存原声，用于生活瞬间分享和服务器端转写。
```

## 开发限制

- Apple Watch 只能读取 HealthKit 提供的心率样本，不读取原始 PPG 波形；
- Watch 端触觉只能近似重现节奏，不能控制为任意马达波形；
- WatchConnectivity 只连接同一用户配对的 Watch 与 iPhone，异地传输必须经过服务器；
- 原声在 iPhone 中落盘后再上传，服务端负责 ASR；设备端不做本地转写；
- 当前后端使用 `bpm` 与逗号分隔的 `pattern`，Apple 端内部仍保留规范字段，映射集中在 `BackendHeartbeatSendRequest`；
- 当前语音上传接口未返回服务端测得的时长，因此 UI 暂以 10 秒占位，后续应由录音元数据提供准确时长。

## 本地验证

共享核心不依赖 Xcode，可运行：

```bash
cd apple
swift test
```

iOS、watchOS、HealthKit 和 WatchConnectivity 必须在完整 Xcode 与真机环境中验证。

无签名模拟器构建：

```bash
xcodebuild \
  -project Gongzai.xcodeproj \
  -scheme GongzaiIOS \
  -sdk iphonesimulator \
  -destination 'generic/platform=iOS Simulator' \
  CODE_SIGNING_ALLOWED=NO build
```
