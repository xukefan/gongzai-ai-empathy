# Apple 端开发说明

本目录对应成员 1 负责的 iPhone 与 Apple Watch 原型。当前交付先完成：

1. Apple Watch 主动采集一段心率；
2. Watch 将心率片段和原声文件传给配对的 iPhone；
3. iPhone 通过临时适配层调用当前后端接口；
4. 接收端 Watch 按 BPM 使用系统触觉重现心跳节奏。

手表负责震动；挂件不包含振动马达，只用 LED 呈现心跳频率并播放原声。

## 目录

```text
apple/
├── Sources/GongzaiCore/    # 两端共享的数据模型、计算和接口适配
├── Tests/                  # 与 Apple 平台无关的单元测试
├── ios/                    # iPhone App 文件
└── watch/                  # Apple Watch App 文件
```

## Xcode 工程接入

仓库暂不提交个人签名信息和 `xcuserdata`。请在安装完整 Xcode 的 Mac 上：

1. 新建一个 SwiftUI iOS App；
2. 在同一工程增加 `Watch App for iOS App` target；
3. 将 `ios/` 文件加入 iOS target，将 `watch/` 文件加入 watchOS target；
4. 通过 `File > Add Package Dependencies > Add Local` 添加本目录；
5. 两个 target 均依赖 `GongzaiCore`；
6. 在 watchOS target 启用 HealthKit；
7. 若使用活动会话持续采集，启用相应的 Background Modes；
8. 添加心率读取和麦克风用途说明；
9. 使用一组真实配对的 iPhone 与 Apple Watch 验证。

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
