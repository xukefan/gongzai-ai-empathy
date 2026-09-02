# 成员 1 基础实现状态

负责人范围：Apple Watch、iPhone、T5AI 挂件本地核心与总体联调。

## 已完成

### Apple 共享核心

- 统一 `HeartbeatPacket`、生活瞬间草稿和事件状态；
- 过滤异常 BPM、计算平均 BPM 和灯光/触觉间隔；
- 在 API 边界适配后端的 `bpm` 与 `pattern` 字段；
- 已添加并通过共享核心测试。

### Apple Watch 与 iPhone

- 已建立可运行的 iOS 与 watchOS 工程；
- Watch App 已作为 Companion App 嵌入 iPhone App；
- 已实现 HealthKit 授权、短时心率采集和 BPM 页面；
- 已实现 WatchConnectivity 心率、原声文件和确认消息传输；
- 已实现 Watch 系统触觉心跳节奏；
- iPhone 已适配公网 FastAPI 健康检查、心跳、语音和勿扰接口；
- iOS 与 watchOS 工程均已在 Xcode 中编译成功；
- Apple 共享核心测试全部通过。

### T5AI 挂件

- 3.5 英寸触摸屏、板载 LED、扬声器、麦克风和物理按键已接入；
- 60、80、100 BPM 灯光脉动可本地演示；
- 已实现触摸确认和带唯一 `event_id` 的状态流；
- 已实现本地测试原声播放；
- 按住按钮采集 16 kHz PCM，松开后在 PSRAM 中封装最长 15 秒 WAV；
- 普通测试和内存安全测试全部通过；
- 已生成可烧录的 T5AI 固件。

## 当前联调环境

- 后端地址：`http://124.221.238.246:8000`；
- 健康检查、OpenAPI、时间线和勿扰读取已验证可访问；
- 当前地址为明文 HTTP，仅用于开发联调，正式测试前必须迁移 HTTPS；
- 挂件通过 Wi-Fi/Tuya 云通信，BLE 只用于配网和本地维护。

## 待完成

- 在 Watch 真机确认修复后的实时 BPM 持续显示和发送；
- 验证 Watch 原声文件可靠传给 iPhone；
- 接入 Tuya 产品 PID、设备授权和最终 DP；
- 打通服务器到挂件的 BPM、`event_id` 和原声任务；
- 挂件使用 HTTPS 上传回复 WAV；
- 打通挂件确认与回复回传到 Apple Watch；
- 与服务端 ASR、AI 标题、摘要、标签和回忆工作流联调。

## 验收命令

```bash
cd apple
swift test

cd ../pendant
cmake -S . -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Apple HealthKit、WatchConnectivity、触觉和录音必须继续使用真实 iPhone 与 Apple Watch 验证。
