# 实体挂件开发说明

实体挂件由成员 1 负责，比赛版采用 T5AI 开发板。当前技术边界已经固定：

- 通过 Wi-Fi 接入涂鸦云，BLE 仅用于首次配网；
- LED 按真实心率频率闪烁，不使用振动马达；
- 扬声器播放发送者保存的原声；
- 用户轻触表示“已收到”；
- 可选按住按钮录制原声回复；
- 音频上传到服务器后统一 ASR，不使用外挂 ASR 模块，也不在挂件本地转写。

## 本目录完成的内容

`src/` 与 `include/` 是不依赖具体开发板的可测试核心：

- `heartbeat_light`：将 30～240 BPM 转换成 LED 脉冲周期；
- `pendant_controller`：管理收到片段、播放原声、触摸确认、按键录音、上传回复等状态；
- `tests/`：使用假的硬件接口验证状态流和灯光时序。

编译测试：

```bash
cmake -S pendant -B pendant/build
cmake --build pendant/build
ctest --test-dir pendant/build --output-on-failure
```

## T5AI 真机程序

`tuyaopen/` 已把硬件无关核心接入真实 TUYA_T5AI_BOARD。当前实现：

- 3.5 英寸 ILI9488 + GT1151 触摸屏界面；
- 屏幕逻辑分辨率为 320×480（竖屏），界面根据 LVGL 实际分辨率自适应，避免内容贴近边缘被裁切；
- 使用 TuyaOpen 自带中文字体，显示标题、状态、心率和操作按钮；
- 屏幕光团按 60/80/100 BPM 柔和脉动；
- 板载 GPIO LED 按同一 BPM 亮灭；
- 板载扬声器播放 TuyaOpen 官方内嵌 MP3，验证原声播放链路；
- 板载麦克风仅在用户按住回复按钮时采集 16 kHz PCM；
- 松开后在 PSRAM 中封装标准 WAV，最长 15 秒，不把私密原声落盘；
- 屏幕和物理按键确认“已收到”；
- 屏幕长按与物理按键长按控制真实录音，并生成待上传音频资产；
- 事件始终携带明确 `event_id`。

适配状态：

| 接口 | T5AI 上的职责 |
|---|---|
| `set_led_brightness` | 已接入屏幕光团和板载 GPIO LED；外接灯环后再换 PWM 驱动 |
| `play_audio` | 已接入板载扬声器和内存 MP3；网络原声下载待接入 |
| `start_recording` | 已接入板载麦克风 PCM 采集，按住才启用 |
| `stop_recording` | 已在 PSRAM 封装 16 kHz/16-bit/单声道 WAV |
| `upload_recording` | 已暴露内存 WAV 的地址和长度；HTTPS 与服务器鉴权待接入 |
| `report_state` | 当前写串口日志；涂鸦 DP 上报待接入 |
| `now_ms` | 已接入 `tal_system_get_millisecond()` |

后续云端收到新片段时，适配层仍按以下方式转换为业务事件：

```c
pendant_controller_receive_moment(
    &controller,
    event_id,
    bpm,
    heartbeat_duration_ms,
    audio_ref
);
```

LVGL 定时器每 20 ms 调用一次：

```c
pendant_controller_tick(&controller);
```

## 第一版物料

- T5AI 开发板；
- 可调光 LED 或 LED 灯环；
- 限流电阻/合适的 LED 驱动；
- 板载或外接扬声器；
- 板载麦克风；
- 触摸传感器；
- 可选实体录音按键；
- USB 供电。

## 编译与烧录

要求先安装并初始化 TuyaOpen SDK，然后执行：

```bash
cd /path/to/TuyaOpen
source ./export.sh
cd /path/to/gongzai-ai-empathy/pendant/tuyaopen

tos.py build
tos.py flash -p /dev/cu.usbmodemXXXXXXXXXXXX
tos.py monitor -p /dev/cu.usbmodemYYYYYYYYYYYY
```

`CMakeLists.txt` 会复用当前 TuyaOpen SDK 自带的 `hello_tuya_16k.c` 作为扬声器测试原声，不把第三方二进制和构建产物提交进仓库。

阶段一已完成 LED、屏幕、触摸、按钮、本地音频播放和麦克风录音封装。

## Tuya 云端桥接（当前进度）

`tuyaopen/src/tuya_cloud_bridge.c` 已接入 TuyaOpen 的云端 worker：

- 启动 Tuya IoT、Wi-Fi 配网和串口授权 CLI；
- 接收 DP 101 `bpm` 作为待执行参数，在应用线程中转换为 LED 心跳；
- 接收 DP 102 `pattern` 并记录，后续可扩展为自定义节奏；
- 接收 DP 103 `trigger`，触发一次默认心率片段；
- 用户触摸/按键确认后，排队上报 DP 104 `touch_ack`；
- 云回调不直接操作 LVGL，避免线程安全问题。

当前产品 PID 为 `irvw50xfd7hcgyw7`。UUID/AuthKey 只允许通过以下任一方式提供，不能提交到 GitHub：

1. 使用 `tyutool_cli authorize` 写入开发板 KV（推荐）；
2. 本地创建被 `.gitignore` 忽略的 `tuya_config_secrets.h`。

烧录后可先确认授权状态：

```bash
tyutool_cli authorize --plain --device t5ai \
  --port /dev/cu.usbmodemXXXXXXXXXXXX
```

设备完成授权后，通过 Tuya App 进行 Wi-Fi 配网；配网成功且 MQTT 连接后，从产品调试面板先设置 DP 101（必要时再设置 DP 102），最后将 DP 103 `trigger` 设为 `true` 才会执行一次 LED 心跳。这样可以避免后端按 `bpm → pattern → trigger` 下发时重复执行。DP 101 的范围为 30～240，DP 104 为只读枚举反馈。

注意：本固件仍是“云端心率 + LED”联调版本，网络原声下载/播放、录音回复上传和服务器 HTTPS 还未合入；这些功能必须在云桥稳定后再接入。
