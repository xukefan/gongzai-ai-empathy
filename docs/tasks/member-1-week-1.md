# 成员 1 第一周实现记录

负责人范围：Apple Watch、iPhone、T5AI 挂件本地核心与总体联调。

## 已完成的仓库代码

### Apple 共享核心

- 统一 `HeartbeatPacket`、`MomentDraft` 和事件状态；
- 过滤异常 BPM、计算平均 BPM 和灯光/触觉间隔；
- 保留规范字段，在 API 边界临时适配当前后端的 `bpm/pattern`；
- 添加共享核心测试。

### Apple Watch

- HealthKit 授权与 `HKWorkoutSession` 短时心率采集；
- 将心率样本生成统一心跳事件；
- 使用 WatchConnectivity 将事件传给配对 iPhone；
- 使用系统触觉按收到的 BPM 播放心跳节奏；
- 通过 AVFoundation 录制原声并传给 iPhone；
- 接收“对方已收到”确认。

### iPhone

- 接收并持久保存 Watch 传来的心率和原声文件；
- 通过 API Client 将心率事件映射到当前后端；
- 通过 multipart 上传原声，交给服务器统一 ASR；
- 提供最小调试页面和服务器地址配置。

### 挂件核心

- 将 30～240 BPM 转换为 LED 快亮慢熄的脉冲；
- 接收带 `event_id`、BPM 和原声资源标识的生活瞬间；
- 管理原声播放、轻触确认、按下录音、松开上传和失败状态；
- 通过 HAL 隔离 TuyaOpen 与具体硬件；
- 使用普通 C 单元测试验证灯光算法和回复状态流。

## 真机进度（2026-08-07）

- [ ] 在完整 Xcode 中创建 iOS + watchOS targets 并加入现有源码；
- [ ] 在真实 Apple Watch 上授权并采集 10～15 秒心率；
- [ ] 验证 Watch 原声文件可靠传给 iPhone；
- [ ] 用真实后端地址验证 iPhone 心率与音频上传；
- [x] 在 T5AI 上实现屏幕灯光、板载 LED、扬声器、按钮和时钟 HAL；
- [x] 在 T5AI 上实现真实麦克风录音和内存 WAV 封装；
- [ ] 接入 TuyaOpen Wi-Fi 配网和规范 DP；
- [x] 使用 60、80、100 BPM 检查三种 LED 节奏；
- [x] 验证挂件本地播放测试原声；
- [ ] 真机按住录音、松开后确认 WAV 字节数、时长和声音峰值；
- [ ] 与成员 2 联调明确 `event_id` 的确认和回复链路。

当前 T5AI 固件位于 `pendant/tuyaopen/`，并已在 TUYA_T5AI_BOARD 3.5 英寸触摸屏版本上完成编译和烧录。串口日志确认：

- LCD、GT1151 触摸驱动和 LVGL 启动成功；
- 音频编解码器、AEC 和 AI Player 启动成功；
- 板载麦克风以 16 kHz、16-bit、单声道 PCM 启动，15 秒录音缓冲分配成功；
- 默认 `demo-0001` 以 80 BPM 运行；
- 屏幕与板载 LED 按 BPM 持续脉动；
- 触摸 `PLAY VOICE` 后 MP3 解码和扬声器播放完成；
- `I FELT IT` 可把事件状态切换为 `ACKNOWLEDGED`；
- 60/80/100 BPM 按钮可创建带唯一 `event_id` 的新演示事件。

录音实现不会把私密原声写入 Flash 或文件系统。松开回复按钮后，固件在 PSRAM 中生成标准 WAV，并通过 `memory://gongzai-reply.wav` 暴露给后续 HTTPS 上传层。当前全量固件已编译、烧录并确认麦克风初始化；最后一次人工按住录音验收仍需在开发板上完成。

## 暂时阻塞

- 当前执行环境只有 Command Line Tools，没有完整 Xcode 和 Apple 平台 SDK，无法代替真机验证 HealthKit、AVFoundation 与 WatchConnectivity；
- T5AI 的录音与 WAV 封装已经接入；真实 HTTPS 上传仍等待成员 2 提供鉴权接口；
- Tuya 产品 PID、授权信息和最终 DP 尚未确定，暂未连接设备云；
- 现有后端接口会重新生成 `event_id`，且挂件回应按“最近事件”关联，不满足端到端事件一致性，联调前需要成员 2 修正。

## 验收命令

```bash
cd apple
swift build

cd ..
cmake -S pendant -B pendant/build
cmake --build pendant/build
ctest --test-dir pendant/build --output-on-failure
```

完整 Apple 单元测试需在安装 Xcode 后运行 `swift test`。
