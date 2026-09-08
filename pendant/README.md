# 实体挂件开发说明

实体挂件由成员 1 负责，比赛版采用 T5AI 开发板。当前技术边界已经固定：

- 通过 Wi-Fi 直接连接 FastAPI；BLE 仅用于首次配网；涂鸦 DP 保留为兼容层；
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
| `play_audio` | 已接入板载扬声器、内存 MP3 和服务器签名 MP3 URL |
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

## FastAPI 直连（当前主链路）

`tuyaopen/src/pendant_http_bridge.c` 已实现：

- 每 2.5 秒查询一次待播放事件；
- 按 `device_id` 取得 BPM、`event_id` 与可选原声引用；
- 将事件送入 LED 心跳状态机；
- 心跳事件在挂件接受后回传 `played`；带原声事件通过短期签名 MP3 URL 播放，并在播放器结束后回传 `played`；
- 用户触摸后回传 `touch`；
- 获取事件后服务端保持事件为 `created`，直到挂件确认；网络或播放失败时挂件释放本地占用，服务端会重试，避免静默丢失片段。

服务器地址、设备 ID 和访问令牌通过本地 `tuya_config_secrets.h` 覆盖，示例：

```c
#define GONGZAI_API_HOST "api.example.com"
#define GONGZAI_API_PORT 443U
#define GONGZAI_PENDANT_DEVICE_ID "pendant-a"
#define GONGZAI_PENDANT_API_TOKEN "replace-locally"
```

真实令牌不能提交到 GitHub。当前服务器仍为 HTTP，适合临时联调，不适合承载正式用户原声；上线前必须配置域名和 HTTPS。

## Tuya 云端桥接（可选兼容层）

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

当前直连版已能跑通“心率事件 + LED + 触摸回应”，服务器会将上传的原始录音保留给 ASR/日记，同时生成 16 kHz 单声道 MP3 供 T5 播放。挂件通过事件级短期签名 URL 获取 MP3；原始录音不会通过挂件接口直接暴露。录音回复的 multipart 上传和服务器 HTTPS 仍需继续接入，当前 HTTP 仅用于开发联调。
