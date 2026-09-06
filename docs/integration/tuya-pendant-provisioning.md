# Tuya 挂件配网与 DP 联调

本文用于把 T5AI 开发板接入 `Gongzai Pendant` 产品，并验证“云端下发心率 → 挂件 LED 闪烁 → 用户确认回传”的闭环。

## 1. 当前产品信息

- 产品：`Gongzai Pendant`
- PID：`irvw50xfd7hcgyw7`
- 通信：Wi-Fi；BLE 仅用于首次配网
- 固件：`pendant/tuyaopen/`

DP 约定：

| DP | 标识 | 方向 | 作用 |
|---:|---|---|---|
| 101 | `bpm` | 云端 → 设备 | 暂存心率，范围 30–240 |
| 102 | `pattern` | 云端 → 设备 | 暂存自定义节奏字符串，当前仅记录日志 |
| 103 | `trigger` | 云端 → 设备 | 为 `true` 时执行一次 LED 心跳 |
| 104 | `touch_ack` | 设备 → 云端 | 用户确认反馈：`tap` 或 `touch` |

重要：DP 101 和 DP 102 只是准备参数，必须最后下发 DP 103，才会执行一次。这样可以避免后端按 `bpm → pattern → trigger` 下发时重复播放。

## 2. 烧录前检查

授权信息只写入开发板安全 KV，不进入源码和 GitHub。烧录后可在本机确认授权状态，但不要把命令输出中的 UUID/AuthKey 发到群里或提交到仓库。

```bash
tyutool_cli authorize --plain --device t5ai \
  --port /dev/cu.usbmodemXXXXXXXXXXXX
```

开发板的控制串口和日志串口可能不同。以当前板子为例：

- 控制/烧录：`/dev/cu.usbmodem5AAE1659911`
- 日志监视：`/dev/cu.usbmodem5AAE1659913`

## 3. 手机配网

1. 保持开发板通电，手机靠近开发板。
2. 打开 Tuya 或 Smart Life App，使用“添加设备/附近设备/BLE 配网”等入口。
3. 如果 App 要求 AP 配网，选择开发板广播出的 `SmartLife-XXXX` 临时热点；当前测试曾出现 `SmartLife-C9A5`，实际后缀可能变化。
4. 选择家庭 Wi-Fi，输入密码并等待设备绑定到 `Gongzai Pendant` 产品。
5. 配网期间不要拔掉开发板，也不要切换到另一块板子。

日志中出现以下信息，才表示云桥真正上线：

```text
Tuya cloud worker started
TUYA_EVENT_MQTT_CONNECTED
Tuya cloud connected
```

只看到 BLE 广播、AP 热点或 `activation mode`，说明仍在配网阶段，还不能进行 DP 测试。

## 4. 产品调试面板测试

设备上线后，在涂鸦开发者平台的产品调试/设备调试面板中按下面顺序操作：

### 4.1 测试 80 BPM

先下发：

```text
DP 101 bpm = 80
```

再下发：

```text
DP 103 trigger = true
```

预期结果：

- 挂件屏幕光团开始按约 80 BPM 脉动；
- 板载 LED 按同一节奏亮灭；
- 串口日志出现 `Cloud BPM staged: 80`；
- 随后出现 `Cloud moment queued`。

### 4.2 测试边界值

分别使用 30、120、240 BPM，确认 LED 频率随参数变化。超出范围的值会被固件限制到 30–240。

### 4.3 测试确认回传

在挂件屏幕点击“我已感受”，或单击实体按键。设备会通过 DP 104 上报 `tap`。

预期结果：

- 串口出现触摸/确认日志；
- 产品调试面板收到 DP 104；
- 后端收到对应事件后，可将心跳事件更新为已回应。

## 5. 后端联调顺序

后端发送一条心跳时，顺序应为：

```text
POST /api/heartbeat/send
  → DP 101 bpm
  → DP 102 pattern（可选）
  → DP 103 trigger=true
```

后端必须把一次请求对应到唯一 `event_id`，不要在重试时重复创建事件。挂件端只在 `trigger=true` 时创建一次本地片段。

## 6. 常见问题

### 看不到设备

- 确认板子仍通电；
- 手机打开蓝牙和局域网权限；
- 关闭之前绑定过该板子的 App 配网页面；
- 必要时重启板子重新进入配网模式。

### 只有 AP/BLE，没有 MQTT connected

- Wi-Fi 名称或密码错误；
- 手机没有把配网结果提交完成；
- 开发板距离路由器太远；
- 设备尚未绑定到正确产品；
- 授权信息未写入当前这块板子的 KV。

### DP 下发成功但 LED 不动

- 是否先下发 101，再下发 103；
- `trigger` 是否为布尔 `true`，而不是字符串；
- 查看日志中是否出现 `Cloud moment queued`；
- 确认固件版本是最新构建版本，而不是旧固件。

### 设备回传没有到后端

- DP 104 必须是只读枚举；
- 确认 Tuya 云端消息订阅/回调已经配置；
- 检查设备 ID 是否已绑定到正确用户；
- 后端回调应根据 `device_id` 和 `dp_id=104` 记录回应。

## 7. 当前明确未完成项

- 挂件从服务器下载并播放真实原声；
- 挂件录音 WAV 通过 HTTPS 上传到服务器；
- DP 102 自定义节奏真正驱动 LED；
- Tuya 云端事件自动转发到业务服务器的生产配置。

这些功能应在“MQTT connected + DP 101/103/104 闭环”稳定后再接入，避免同时排查配网、云端和音频问题。
