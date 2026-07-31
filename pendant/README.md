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

## T5AI 适配层待接入

获得开发板和 TuyaOpen SDK 后，需要为 `pendant_hal_t` 实现：

| 接口 | T5AI 上的职责 |
|---|---|
| `set_led_brightness` | PWM 控制 LED 亮度 |
| `play_audio` | 下载或读取原声音频并通过扬声器播放 |
| `start_recording` | 初始化板载麦克风与音频缓存 |
| `stop_recording` | 封装音频并返回本地临时文件 |
| `upload_recording` | 通过 HTTPS 上传原声与明确的 `event_id` |
| `report_state` | 通过涂鸦 DP 上报播放、确认和回复状态 |
| `now_ms` | 返回系统单调毫秒时钟 |

云端收到新片段时，适配层将 DP/业务消息转换为：

```c
pendant_controller_receive_moment(
    &controller,
    event_id,
    bpm,
    heartbeat_duration_ms,
    audio_ref
);
```

主循环或定时任务每 10～20 ms 调用一次：

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

第一周只要求 LED 本地按输入 BPM 闪烁、按钮/触摸状态机可运行。联网、音频播放和录音在接口确定后逐项接入。
