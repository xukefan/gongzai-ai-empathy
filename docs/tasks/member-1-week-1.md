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

## 真机与硬件到货后完成

- [ ] 在完整 Xcode 中创建 iOS + watchOS targets 并加入现有源码；
- [ ] 在真实 Apple Watch 上授权并采集 10～15 秒心率；
- [ ] 验证 Watch 原声文件可靠传给 iPhone；
- [ ] 用真实后端地址验证 iPhone 心率与音频上传；
- [ ] 在 T5AI 上实现 LED PWM、扬声器、麦克风、按钮和时钟 HAL；
- [ ] 接入 TuyaOpen Wi-Fi 配网和规范 DP；
- [ ] 使用 60、80、100 BPM 检查三种 LED 节奏；
- [ ] 验证挂件本地播放测试原声；
- [ ] 验证按住录音、松开生成本地文件；
- [ ] 与成员 2 联调明确 `event_id` 的确认和回复链路。

## 暂时阻塞

- 当前执行环境只有 Command Line Tools，没有完整 Xcode 和 Apple 平台 SDK，无法代替真机验证 HealthKit、AVFoundation 与 WatchConnectivity；
- T5AI 开发板和 TuyaOpen 工程尚未接入，因此本周先交付可测试的硬件无关核心；
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
