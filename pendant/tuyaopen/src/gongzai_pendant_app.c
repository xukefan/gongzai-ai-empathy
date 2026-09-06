/**
 * @file gongzai_pendant_app.c
 * @brief T5AI hardware adapter and interactive pendant prototype.
 */

#include "tuya_cloud_types.h"

#include "app_media.h"
#include "board_com_api.h"
#include "gongzai/pendant_controller.h"
#include "lv_vendor.h"
#include "lvgl.h"
#include "pendant_recorder.h"
#include "svc_ai_player.h"
#include "tal_api.h"
#include "tdl_audio_manage.h"
#include "tdl_button_manage.h"
#include "tdl_led_manage.h"
#include "tkl_output.h"

#include <stdio.h>
#include <string.h>

extern const lv_font_t font_puhui_16_4;

#define HEARTBEAT_DEMO_DURATION_MS (30U * 1000U)
#define HEARTBEAT_TICK_MS          20U
#define PHYSICAL_LED_ON_LEVEL      48U
#define TEST_AUDIO_REF             "embedded://hello-tuya"

typedef enum {
    PENDING_BUTTON_NONE = 0,
    PENDING_BUTTON_ACKNOWLEDGE,
    PENDING_BUTTON_RECORD_START,
    PENDING_BUTTON_RECORD_STOP,
} pending_button_action_t;

static pendant_controller_t sg_controller;
static TDL_LED_HANDLE_T sg_led_handle = NULL;
static TDL_BUTTON_HANDLE sg_button_handle = NULL;
static TDL_AUDIO_HANDLE_T sg_audio_handle = NULL;
static AI_PLAYER_HANDLE sg_player = NULL;
static AI_PLAYLIST_HANDLE sg_playlist = NULL;

static lv_obj_t *sg_pulse_orb = NULL;
static lv_obj_t *sg_bpm_label = NULL;
static lv_obj_t *sg_state_label = NULL;
static lv_obj_t *sg_event_label = NULL;
static lv_obj_t *sg_reply_button = NULL;
static lv_obj_t *sg_reply_button_label = NULL;

static volatile pending_button_action_t sg_pending_button_action = PENDING_BUTTON_NONE;
static uint16_t sg_selected_bpm = 80U;
static uint32_t sg_event_sequence = 0U;
static uint8_t sg_last_led_level = 0U;
static bool sg_physical_led_on = false;
static bool sg_audio_ready = false;
static uint32_t sg_last_reply_size = 0U;

static const char *pendant_state_name(pendant_state_t state)
{
    switch (state) {
    case PENDANT_STATE_IDLE:
        return "IDLE";
    case PENDANT_STATE_INCOMING:
        return "INCOMING";
    case PENDANT_STATE_PLAYING:
        return "PLAYING VOICE";
    case PENDANT_STATE_ACKNOWLEDGED:
        return "FELT IT";
    case PENDANT_STATE_RECORDING:
        return "RECORDING REPLY";
    case PENDANT_STATE_UPLOADING:
        return "UPLOADING";
    case PENDANT_STATE_REPLIED:
        return "REPLIED";
    case PENDANT_STATE_ERROR:
        return "ERROR";
    default:
        return "UNKNOWN";
    }
}

static const char *pendant_state_name_zh(pendant_state_t state)
{
    switch (state) {
    case PENDANT_STATE_IDLE:
        return "空闲";
    case PENDANT_STATE_INCOMING:
        return "收到片段";
    case PENDANT_STATE_PLAYING:
        return "播放语音";
    case PENDANT_STATE_ACKNOWLEDGED:
        return "已感受到";
    case PENDANT_STATE_RECORDING:
        return "录制回复";
    case PENDANT_STATE_UPLOADING:
        return "上传中";
    case PENDANT_STATE_REPLIED:
        return "已回复";
    case PENDANT_STATE_ERROR:
        return "发生错误";
    default:
        return "未知状态";
    }
}

static uint32_t pendant_now_ms(void)
{
    return (uint32_t)tal_system_get_millisecond();
}

static void update_physical_led(uint8_t level)
{
    OPERATE_RET rt;
    bool should_be_on;

    if (sg_led_handle == NULL) {
        return;
    }

    should_be_on = level >= PHYSICAL_LED_ON_LEVEL;
    if (should_be_on == sg_physical_led_on) {
        return;
    }

    sg_physical_led_on = should_be_on;
    TUYA_CALL_ERR_LOG(tdl_led_set_status(
        sg_led_handle,
        should_be_on ? TDL_LED_ON : TDL_LED_OFF
    ));
}

static void pendant_set_led_brightness(uint8_t level)
{
    uint8_t opacity;
    uint8_t red;
    uint8_t green;
    uint8_t blue;

    sg_last_led_level = level;
    update_physical_led(level);

    if (sg_pulse_orb == NULL) {
        return;
    }

    opacity = (uint8_t)(55U + ((uint16_t)level * 200U) / 255U);
    red = (uint8_t)(30U + ((uint16_t)level * 75U) / 255U);
    green = (uint8_t)(95U + ((uint16_t)level * 95U) / 255U);
    blue = (uint8_t)(150U + ((uint16_t)level * 105U) / 255U);

    lv_obj_set_style_bg_color(
        sg_pulse_orb,
        lv_color_make(red, green, blue),
        LV_PART_MAIN
    );
    lv_obj_set_style_bg_opa(sg_pulse_orb, opacity, LV_PART_MAIN);
    lv_obj_set_style_shadow_width(
        sg_pulse_orb,
        8 + ((int32_t)level * 24) / 255,
        LV_PART_MAIN
    );
    lv_obj_set_style_shadow_opa(sg_pulse_orb, opacity, LV_PART_MAIN);
}

static OPERATE_RET pendant_audio_init(void)
{
    OPERATE_RET rt;
    AI_PLAYER_CFG_T player_cfg = {
        .sample = 16000,
        .datebits = 16,
        .channel = 1,
    };
    AI_PLAYLIST_CFG_T playlist_cfg = {
        .auto_play = true,
        .capacity = 2,
    };

    rt = tdl_audio_find(AUDIO_CODEC_NAME, &sg_audio_handle);
    if (rt != OPRT_OK) {
        PR_ERR("Audio codec not found: %d", rt);
        return rt;
    }

    TUYA_CALL_ERR_RETURN(pendant_recorder_open(sg_audio_handle));
    TUYA_CALL_ERR_RETURN(tuya_ai_player_service_init(&player_cfg));
    TUYA_CALL_ERR_RETURN(tuya_ai_player_create(
        AI_PLAYER_MODE_FOREGROUND,
        &sg_player
    ));
    TUYA_CALL_ERR_RETURN(tuya_ai_playlist_create(
        sg_player,
        &playlist_cfg,
        &sg_playlist
    ));

    TUYA_CALL_ERR_LOG(tdl_audio_volume_set(sg_audio_handle, 65));
    sg_audio_ready = true;
    PR_NOTICE("Pendant speaker initialized");
    return OPRT_OK;
}

static bool pendant_play_audio(const char *audio_ref)
{
    OPERATE_RET rt;

    if (!sg_audio_ready || audio_ref == NULL) {
        PR_ERR("Cannot play audio: speaker is not ready");
        return false;
    }

    if (strcmp(audio_ref, TEST_AUDIO_REF) != 0) {
        PR_ERR("Unsupported local audio reference: %s", audio_ref);
        return false;
    }

    TUYA_CALL_ERR_LOG(tuya_ai_playlist_stop(sg_playlist));
    TUYA_CALL_ERR_LOG(tuya_ai_player_start(
        sg_player,
        AI_PLAYER_SRC_MEM,
        NULL,
        AI_AUDIO_CODEC_MP3
    ));
    TUYA_CALL_ERR_LOG(tuya_ai_player_feed(
        sg_player,
        (uint8_t *)media_src_hello_tuya_16k,
        sizeof(media_src_hello_tuya_16k)
    ));
    TUYA_CALL_ERR_LOG(tuya_ai_player_feed(sg_player, NULL, 0));
    PR_NOTICE("Playing embedded original-voice test audio");
    return true;
}

static bool pendant_start_recording(const char *event_id)
{
    OPERATE_RET rt;

    if (!sg_audio_ready || event_id == NULL) {
        return false;
    }

    TUYA_CALL_ERR_LOG(tuya_ai_playlist_stop(sg_playlist));
    TUYA_CALL_ERR_LOG(tdl_audio_play_stop(sg_audio_handle));
    if (!pendant_recorder_start()) {
        PR_ERR("Unable to start reply recording for event: %s", event_id);
        return false;
    }

    PR_NOTICE("Recording reply for event: %s", event_id);
    return true;
}

static bool pendant_stop_recording(char *path, size_t capacity)
{
    if (path == NULL || capacity <= strlen(PENDANT_RECORDER_WAV_URI)) {
        return false;
    }

    if (!pendant_recorder_stop()) {
        return false;
    }

    (void)strcpy(path, PENDANT_RECORDER_WAV_URI);
    sg_last_reply_size = pendant_recorder_wav_size();
    PR_NOTICE(
        "Reply recording stopped: %s, %u bytes, %u ms",
        path,
        sg_last_reply_size,
        pendant_recorder_duration_ms()
    );
    return true;
}

static bool pendant_upload_recording(
    const char *event_id,
    const char *recording_path
)
{
    const uint8_t *wav_data = pendant_recorder_wav_data();
    uint32_t wav_size = pendant_recorder_wav_size();

    if (event_id == NULL || recording_path == NULL ||
        strcmp(recording_path, PENDANT_RECORDER_WAV_URI) != 0 ||
        wav_data == NULL || wav_size <= 44U) {
        PR_ERR("Reply WAV asset is unavailable for upload");
        return false;
    }

    PR_NOTICE(
        "Upload-ready WAV asset: event=%s path=%s bytes=%u peak=%u",
        event_id,
        recording_path,
        wav_size,
        pendant_recorder_peak_amplitude()
    );

    /*
     * The foundation milestone stops at a verified upload-ready memory asset.
     * Member 2 will provide the authenticated HTTP endpoint in the next
     * integration milestone. Never print or persist the private voice bytes.
     */
    return true;
}

static void pendant_report_state(
    const char *event_id,
    pendant_state_t state
)
{
    PR_NOTICE(
        "Pendant state: event=%s state=%s",
        event_id != NULL ? event_id : "",
        pendant_state_name(state)
    );
}

static void update_ui_from_controller(void)
{
    if (sg_bpm_label != NULL) {
        lv_label_set_text_fmt(sg_bpm_label, "心率 %u", sg_selected_bpm);
    }

    if (sg_state_label != NULL) {
        lv_label_set_text_fmt(
            sg_state_label,
            "状态：%s",
            pendant_state_name_zh(sg_controller.state)
        );
    }

    if (sg_event_label != NULL) {
        if (sg_last_reply_size > 0U) {
            lv_label_set_text_fmt(
                sg_event_label,
                "回复已录制\n等待上传接入"
            );
        } else {
            lv_label_set_text_fmt(
                sg_event_label,
                "%s",
                sg_controller.has_active_event ? "本地体验 · 心率与原声" : "选择节奏，体验这一刻"
            );
        }
    }

    if (sg_reply_button_label != NULL) {
        lv_label_set_text(
            sg_reply_button_label,
            sg_controller.state == PENDANT_STATE_RECORDING
                ? "松开结束录音"
                : "按住回复"
        );
    }
}

static void receive_demo_moment(uint16_t bpm)
{
    char event_id[GONGZAI_EVENT_ID_CAPACITY];

    sg_selected_bpm = bpm;
    sg_event_sequence++;
    (void)snprintf(
        event_id,
        sizeof(event_id),
        "demo-%04lu",
        (unsigned long)sg_event_sequence
    );

    if (!pendant_controller_receive_moment(
            &sg_controller,
            event_id,
            bpm,
            HEARTBEAT_DEMO_DURATION_MS,
            ""
        )) {
        PR_ERR("Failed to receive demo moment at %u BPM", bpm);
        return;
    }

    PR_NOTICE("Demo moment received: event=%s bpm=%u", event_id, bpm);
    update_ui_from_controller();
}

static void bpm_button_event_cb(lv_event_t *event)
{
    uint16_t bpm;

    if (lv_event_get_code(event) != LV_EVENT_CLICKED) {
        return;
    }

    bpm = (uint16_t)(uintptr_t)lv_event_get_user_data(event);
    receive_demo_moment(bpm);
}

static void play_voice_event_cb(lv_event_t *event)
{
    if (lv_event_get_code(event) != LV_EVENT_CLICKED) {
        return;
    }

    (void)pendant_play_audio(TEST_AUDIO_REF);
}

static void acknowledge_event_cb(lv_event_t *event)
{
    if (lv_event_get_code(event) != LV_EVENT_CLICKED) {
        return;
    }

    pendant_controller_on_touch(&sg_controller);
    update_ui_from_controller();
}

static void reply_button_event_cb(lv_event_t *event)
{
    lv_event_code_t code = lv_event_get_code(event);

    if (code == LV_EVENT_PRESSED) {
        (void)pendant_controller_on_record_button_pressed(&sg_controller);
    } else if (code == LV_EVENT_RELEASED || code == LV_EVENT_PRESS_LOST) {
        if (pendant_controller_on_record_button_released(&sg_controller)) {
            pendant_controller_on_upload_finished(&sg_controller, true);
        }
    } else {
        return;
    }

    update_ui_from_controller();
}

static lv_obj_t *create_action_button(
    lv_obj_t *parent,
    const char *text,
    lv_event_cb_t event_cb,
    void *user_data
)
{
    lv_obj_t *button = lv_btn_create(parent);
    lv_obj_t *label;

    lv_obj_set_size(button, 112, 42);
    lv_obj_set_style_bg_color(button, lv_color_hex(0x49303C), LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        button,
        lv_color_hex(0xB95870),
        LV_PART_MAIN | LV_STATE_PRESSED
    );
    lv_obj_set_style_radius(button, 13, LV_PART_MAIN);
    lv_obj_add_event_cb(button, event_cb, LV_EVENT_CLICKED, user_data);

    label = lv_label_create(button);
    lv_label_set_text(label, text);
    lv_obj_set_style_text_color(label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_font(label, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_center(label);
    return button;
}

static void pendant_ui_create(void)
{
    lv_obj_t *screen = lv_screen_active();
    lv_display_t *display = lv_display_get_default();
    lv_coord_t screen_width = (lv_coord_t)lv_display_get_horizontal_resolution(display);
    lv_coord_t screen_height = (lv_coord_t)lv_display_get_vertical_resolution(display);
    bool is_portrait = screen_height > screen_width;
    lv_obj_t *title;
    lv_obj_t *subtitle;
    lv_obj_t *button_row;
    lv_obj_t *bpm_button;
    lv_obj_t *action_row;
    lv_obj_t *voice_button;
    lv_obj_t *ack_button;

    lv_obj_set_style_bg_color(screen, lv_color_hex(0x1C1720), LV_PART_MAIN);
    lv_obj_set_style_bg_opa(screen, LV_OPA_COVER, LV_PART_MAIN);

    PR_NOTICE(
        "LVGL display resolution: %ldx%ld (%s)",
        (long)screen_width,
        (long)screen_height,
        is_portrait ? "portrait" : "landscape"
    );

    if (is_portrait) {
        lv_coord_t margin = 12;
        lv_coord_t content_width = screen_width - (margin * 2);
        lv_coord_t orb_size = content_width < 128 ? content_width : 128;

        title = lv_label_create(screen);
        lv_label_set_text(title, "共在 · 情感挂件");
        lv_obj_set_width(title, content_width);
        lv_obj_set_style_text_color(title, lv_color_hex(0xFFF0F3), LV_PART_MAIN);
        lv_obj_set_style_text_font(title, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_set_style_text_align(title, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 8);

        subtitle = lv_label_create(screen);
        lv_label_set_text(subtitle, "本地体验 · 留住这一刻");
        lv_obj_set_width(subtitle, content_width);
        lv_obj_set_style_text_color(subtitle, lv_color_hex(0xB3A2AF), LV_PART_MAIN);
        lv_obj_set_style_text_font(subtitle, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_set_style_text_align(subtitle, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        lv_obj_align(subtitle, LV_ALIGN_TOP_MID, 0, 40);

        sg_pulse_orb = lv_obj_create(screen);
        lv_obj_set_size(sg_pulse_orb, orb_size, orb_size);
        lv_obj_align(sg_pulse_orb, LV_ALIGN_TOP_MID, 0, 72);
        lv_obj_clear_flag(sg_pulse_orb, LV_OBJ_FLAG_SCROLLABLE);
        lv_obj_set_style_radius(sg_pulse_orb, LV_RADIUS_CIRCLE, LV_PART_MAIN);
        lv_obj_set_style_border_width(sg_pulse_orb, 2, LV_PART_MAIN);
        lv_obj_set_style_border_color(sg_pulse_orb, lv_color_hex(0xF09AA9), LV_PART_MAIN);
        lv_obj_set_style_shadow_color(sg_pulse_orb, lv_color_hex(0xF09AA9), LV_PART_MAIN);

        sg_bpm_label = lv_label_create(sg_pulse_orb);
        lv_obj_set_style_text_color(sg_bpm_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_text_font(sg_bpm_label, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_center(sg_bpm_label);

        sg_state_label = lv_label_create(screen);
        lv_obj_set_width(sg_state_label, content_width);
        lv_obj_set_style_text_color(sg_state_label, lv_color_hex(0xF4BBC5), LV_PART_MAIN);
        lv_obj_set_style_text_font(sg_state_label, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_set_style_text_align(sg_state_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        lv_obj_align(sg_state_label, LV_ALIGN_TOP_MID, 0, 207);

        sg_event_label = lv_label_create(screen);
        lv_obj_set_width(sg_event_label, content_width);
        lv_label_set_long_mode(sg_event_label, LV_LABEL_LONG_WRAP);
        lv_obj_set_style_text_color(sg_event_label, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
        lv_obj_set_style_text_font(sg_event_label, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_set_style_text_align(sg_event_label, LV_TEXT_ALIGN_CENTER, LV_PART_MAIN);
        lv_obj_align(sg_event_label, LV_ALIGN_TOP_MID, 0, 235);

        button_row = lv_obj_create(screen);
        lv_obj_set_size(button_row, content_width, 50);
        lv_obj_align(button_row, LV_ALIGN_TOP_MID, 0, 286);
        lv_obj_set_flex_flow(button_row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(
            button_row,
            LV_FLEX_ALIGN_SPACE_EVENLY,
            LV_FLEX_ALIGN_CENTER,
            LV_FLEX_ALIGN_CENTER
        );
        lv_obj_set_style_bg_opa(button_row, LV_OPA_TRANSP, LV_PART_MAIN);
        lv_obj_set_style_border_width(button_row, 0, LV_PART_MAIN);
        lv_obj_set_style_pad_all(button_row, 0, LV_PART_MAIN);

        bpm_button = create_action_button(
            button_row,
            "60次/分",
            bpm_button_event_cb,
            (void *)(uintptr_t)60U
        );
        lv_obj_set_width(bpm_button, (content_width - 12) / 3);
        bpm_button = create_action_button(
            button_row,
            "80次/分",
            bpm_button_event_cb,
            (void *)(uintptr_t)80U
        );
        lv_obj_set_width(bpm_button, (content_width - 12) / 3);
        bpm_button = create_action_button(
            button_row,
            "100次/分",
            bpm_button_event_cb,
            (void *)(uintptr_t)100U
        );
        lv_obj_set_width(bpm_button, (content_width - 12) / 3);

        action_row = lv_obj_create(screen);
        lv_obj_set_size(action_row, content_width, 50);
        lv_obj_align(action_row, LV_ALIGN_BOTTOM_MID, 0, -62);
        lv_obj_set_flex_flow(action_row, LV_FLEX_FLOW_ROW);
        lv_obj_set_flex_align(
            action_row,
            LV_FLEX_ALIGN_SPACE_EVENLY,
            LV_FLEX_ALIGN_CENTER,
            LV_FLEX_ALIGN_CENTER
        );
        lv_obj_set_style_bg_opa(action_row, LV_OPA_TRANSP, LV_PART_MAIN);
        lv_obj_set_style_border_width(action_row, 0, LV_PART_MAIN);
        lv_obj_set_style_pad_all(action_row, 0, LV_PART_MAIN);

        voice_button = create_action_button(
            action_row,
            "播放语音",
            play_voice_event_cb,
            NULL
        );
        lv_obj_set_width(voice_button, (content_width - 12) / 2);

        ack_button = create_action_button(
            action_row,
            "我已感受",
            acknowledge_event_cb,
            NULL
        );
        lv_obj_set_width(ack_button, (content_width - 12) / 2);

        sg_reply_button = lv_btn_create(screen);
        lv_obj_set_size(sg_reply_button, content_width, 42);
        lv_obj_align(sg_reply_button, LV_ALIGN_BOTTOM_MID, 0, -10);
        lv_obj_set_style_bg_color(sg_reply_button, lv_color_hex(0xA4445C), LV_PART_MAIN);
        lv_obj_set_style_bg_color(
            sg_reply_button,
            lv_color_hex(0xCA6E84),
            LV_PART_MAIN | LV_STATE_PRESSED
        );
        lv_obj_set_style_radius(sg_reply_button, 13, LV_PART_MAIN);
        lv_obj_add_event_cb(sg_reply_button, reply_button_event_cb, LV_EVENT_ALL, NULL);

        sg_reply_button_label = lv_label_create(sg_reply_button);
        lv_obj_set_style_text_color(sg_reply_button_label, lv_color_white(), LV_PART_MAIN);
        lv_obj_set_style_text_font(sg_reply_button_label, &font_puhui_16_4, LV_PART_MAIN);
        lv_obj_center(sg_reply_button_label);

        update_ui_from_controller();
        pendant_set_led_brightness(0U);
        return;
    }

    title = lv_label_create(screen);
    lv_label_set_text(title, "共在 · 情感挂件");
    lv_obj_set_style_text_color(title, lv_color_hex(0xFFF0F3), LV_PART_MAIN);
    lv_obj_set_style_text_font(title, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_align(title, LV_ALIGN_TOP_MID, 0, 14);

    subtitle = lv_label_create(screen);
    lv_label_set_text(subtitle, "本地体验 · 留住这一刻");
    lv_obj_set_style_text_color(subtitle, lv_color_hex(0xB3A2AF), LV_PART_MAIN);
    lv_obj_set_style_text_font(subtitle, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_align(subtitle, LV_ALIGN_TOP_MID, 0, 45);

    sg_pulse_orb = lv_obj_create(screen);
    lv_obj_set_size(sg_pulse_orb, 134, 134);
    lv_obj_align(sg_pulse_orb, LV_ALIGN_LEFT_MID, 40, -12);
    lv_obj_clear_flag(sg_pulse_orb, LV_OBJ_FLAG_SCROLLABLE);
    lv_obj_set_style_radius(sg_pulse_orb, LV_RADIUS_CIRCLE, LV_PART_MAIN);
    lv_obj_set_style_border_width(sg_pulse_orb, 2, LV_PART_MAIN);
    lv_obj_set_style_border_color(sg_pulse_orb, lv_color_hex(0xF09AA9), LV_PART_MAIN);
    lv_obj_set_style_shadow_color(sg_pulse_orb, lv_color_hex(0xF09AA9), LV_PART_MAIN);

    sg_bpm_label = lv_label_create(sg_pulse_orb);
    lv_obj_set_style_text_color(sg_bpm_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_font(sg_bpm_label, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_center(sg_bpm_label);

    sg_state_label = lv_label_create(screen);
    lv_obj_set_style_text_color(sg_state_label, lv_color_hex(0xF4BBC5), LV_PART_MAIN);
    lv_obj_set_style_text_font(sg_state_label, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_align(sg_state_label, LV_ALIGN_TOP_LEFT, 210, 91);

    sg_event_label = lv_label_create(screen);
    lv_obj_set_width(sg_event_label, screen_width - 222);
    lv_label_set_long_mode(sg_event_label, LV_LABEL_LONG_WRAP);
    lv_obj_set_style_text_color(sg_event_label, lv_color_hex(0xCBD5E1), LV_PART_MAIN);
    lv_obj_set_style_text_font(sg_event_label, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_align(sg_event_label, LV_ALIGN_TOP_LEFT, 210, 123);

    button_row = lv_obj_create(screen);
    lv_obj_set_size(button_row, 250, 54);
    lv_obj_align(button_row, LV_ALIGN_TOP_LEFT, 202, 155);
    lv_obj_set_flex_flow(button_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(
        button_row,
        LV_FLEX_ALIGN_SPACE_EVENLY,
        LV_FLEX_ALIGN_CENTER,
        LV_FLEX_ALIGN_CENTER
    );
    lv_obj_set_style_bg_opa(button_row, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(button_row, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(button_row, 0, LV_PART_MAIN);

    bpm_button = create_action_button(
        button_row,
        "60",
        bpm_button_event_cb,
        (void *)(uintptr_t)60U
    );
    lv_obj_set_width(bpm_button, 72);
    bpm_button = create_action_button(
        button_row,
        "80",
        bpm_button_event_cb,
        (void *)(uintptr_t)80U
    );
    lv_obj_set_width(bpm_button, 72);
    bpm_button = create_action_button(
        button_row,
        "100",
        bpm_button_event_cb,
        (void *)(uintptr_t)100U
    );
    lv_obj_set_width(bpm_button, 72);

    action_row = lv_obj_create(screen);
    lv_obj_set_size(action_row, 430, 50);
    lv_obj_align(action_row, LV_ALIGN_BOTTOM_MID, 0, -55);
    lv_obj_set_flex_flow(action_row, LV_FLEX_FLOW_ROW);
    lv_obj_set_flex_align(
        action_row,
        LV_FLEX_ALIGN_SPACE_EVENLY,
        LV_FLEX_ALIGN_CENTER,
        LV_FLEX_ALIGN_CENTER
    );
    lv_obj_set_style_bg_opa(action_row, LV_OPA_TRANSP, LV_PART_MAIN);
    lv_obj_set_style_border_width(action_row, 0, LV_PART_MAIN);
    lv_obj_set_style_pad_all(action_row, 0, LV_PART_MAIN);

    voice_button = create_action_button(
        action_row,
        "播放语音",
        play_voice_event_cb,
        NULL
    );
    lv_obj_set_width(voice_button, 130);

    ack_button = create_action_button(
        action_row,
        "我已感受",
        acknowledge_event_cb,
        NULL
    );
    lv_obj_set_width(ack_button, 130);

    sg_reply_button = lv_btn_create(screen);
    lv_obj_set_size(sg_reply_button, 270, 42);
    lv_obj_align(sg_reply_button, LV_ALIGN_BOTTOM_MID, 0, -10);
    lv_obj_set_style_bg_color(sg_reply_button, lv_color_hex(0xA4445C), LV_PART_MAIN);
    lv_obj_set_style_bg_color(
        sg_reply_button,
        lv_color_hex(0xCA6E84),
        LV_PART_MAIN | LV_STATE_PRESSED
    );
    lv_obj_set_style_radius(sg_reply_button, 13, LV_PART_MAIN);
    lv_obj_add_event_cb(sg_reply_button, reply_button_event_cb, LV_EVENT_ALL, NULL);

    sg_reply_button_label = lv_label_create(sg_reply_button);
    lv_obj_set_style_text_color(sg_reply_button_label, lv_color_white(), LV_PART_MAIN);
    lv_obj_set_style_text_font(sg_reply_button_label, &font_puhui_16_4, LV_PART_MAIN);
    lv_obj_center(sg_reply_button_label);

    update_ui_from_controller();
    pendant_set_led_brightness(0U);
}

static void process_pending_physical_button(void)
{
    pending_button_action_t action = sg_pending_button_action;

    sg_pending_button_action = PENDING_BUTTON_NONE;
    switch (action) {
    case PENDING_BUTTON_ACKNOWLEDGE:
        pendant_controller_on_touch(&sg_controller);
        break;
    case PENDING_BUTTON_RECORD_START:
        (void)pendant_controller_on_record_button_pressed(&sg_controller);
        break;
    case PENDING_BUTTON_RECORD_STOP:
        if (pendant_controller_on_record_button_released(&sg_controller)) {
            pendant_controller_on_upload_finished(&sg_controller, true);
        }
        break;
    case PENDING_BUTTON_NONE:
    default:
        break;
    }
}

static void pendant_tick_cb(lv_timer_t *timer)
{
    static uint32_t last_ui_refresh_ms = 0U;
    uint32_t now_ms;

    (void)timer;
    process_pending_physical_button();
    pendant_controller_tick(&sg_controller);

    now_ms = pendant_now_ms();
    if ((uint32_t)(now_ms - last_ui_refresh_ms) >= 200U) {
        last_ui_refresh_ms = now_ms;
        update_ui_from_controller();
    }
}

static void physical_button_event_cb(
    char *name,
    TDL_BUTTON_TOUCH_EVENT_E event,
    void *arg
)
{
    (void)arg;

    switch (event) {
    case TDL_BUTTON_PRESS_SINGLE_CLICK:
        sg_pending_button_action = PENDING_BUTTON_ACKNOWLEDGE;
        PR_NOTICE("%s: acknowledge", name);
        break;
    case TDL_BUTTON_LONG_PRESS_START:
        sg_pending_button_action = PENDING_BUTTON_RECORD_START;
        PR_NOTICE("%s: start reply recording", name);
        break;
    case TDL_BUTTON_PRESS_UP:
        if (sg_controller.state == PENDANT_STATE_RECORDING) {
            sg_pending_button_action = PENDING_BUTTON_RECORD_STOP;
            PR_NOTICE("%s: stop reply recording", name);
        }
        break;
    default:
        break;
    }
}

static OPERATE_RET pendant_peripherals_init(void)
{
    OPERATE_RET rt;
    TDL_BUTTON_CFG_T button_cfg = {
        .long_start_valid_time = 900,
        .long_keep_timer = 500,
        .button_debounce_time = 50,
        .button_repeat_valid_count = 2,
        .button_repeat_valid_time = 350,
    };

    sg_led_handle = tdl_led_find_dev(LED_NAME);
    if (sg_led_handle != NULL) {
        TUYA_CALL_ERR_LOG(tdl_led_open(sg_led_handle));
        TUYA_CALL_ERR_LOG(tdl_led_set_status(sg_led_handle, TDL_LED_OFF));
    } else {
        PR_WARN("Board LED not found; screen pulse remains available");
    }

    rt = tdl_button_create(BUTTON_NAME, &button_cfg, &sg_button_handle);
    if (rt == OPRT_OK) {
        tdl_button_event_register(
            sg_button_handle,
            TDL_BUTTON_PRESS_SINGLE_CLICK,
            physical_button_event_cb
        );
        tdl_button_event_register(
            sg_button_handle,
            TDL_BUTTON_LONG_PRESS_START,
            physical_button_event_cb
        );
        tdl_button_event_register(
            sg_button_handle,
            TDL_BUTTON_PRESS_UP,
            physical_button_event_cb
        );
    } else {
        PR_WARN("Board button unavailable: %d", rt);
    }

    return pendant_audio_init();
}

static void pendant_controller_init_or_halt(void)
{
    pendant_hal_t hal = {
        .set_led_brightness = pendant_set_led_brightness,
        .play_audio = pendant_play_audio,
        .start_recording = pendant_start_recording,
        .stop_recording = pendant_stop_recording,
        .upload_recording = pendant_upload_recording,
        .report_state = pendant_report_state,
        .now_ms = pendant_now_ms,
    };

    if (!pendant_controller_init(&sg_controller, &hal)) {
        PR_ERR("Pendant controller initialization failed");
        while (1) {
            tal_system_sleep(1000);
        }
    }
}

void user_main(void)
{
    OPERATE_RET rt;

    tal_log_init(TAL_LOG_LEVEL_DEBUG, 4096, (TAL_LOG_OUTPUT_CB)tkl_log_output);

    PR_NOTICE("Application information:");
    PR_NOTICE("Project name:        %s", PROJECT_NAME);
    PR_NOTICE("App version:         %s", PROJECT_VERSION);
    PR_NOTICE("Compile time:        %s", __DATE__);
    PR_NOTICE("TuyaOpen commit-id:  %s", OPEN_COMMIT);
    PR_NOTICE("Platform chip:       %s", PLATFORM_CHIP);
    PR_NOTICE("Platform board:      %s", PLATFORM_BOARD);

    tal_sw_timer_init();
    TUYA_CALL_ERR_LOG(board_register_hardware());

    pendant_controller_init_or_halt();
    TUYA_CALL_ERR_LOG(pendant_peripherals_init());

    lv_vendor_init(DISPLAY_NAME);
    pendant_ui_create();
    lv_timer_create(pendant_tick_cb, HEARTBEAT_TICK_MS, NULL);
    receive_demo_moment(sg_selected_bpm);

    PR_NOTICE(
        "Pendant prototype ready: %u BPM, LED level %u",
        sg_selected_bpm,
        sg_last_led_level
    );
    lv_vendor_start(5, 1024U * 10U);
}

#if OPERATING_SYSTEM == SYSTEM_LINUX
void main(int argc, char *argv[])
{
    (void)argc;
    (void)argv;
    user_main();
    while (1) {
        tal_system_sleep(500);
    }
}
#else
static THREAD_HANDLE sg_app_thread = NULL;

static void pendant_app_thread(void *arg)
{
    (void)arg;
    user_main();
    tal_thread_delete(sg_app_thread);
    sg_app_thread = NULL;
}

void tuya_app_main(void)
{
    THREAD_CFG_T thread_cfg = {
        .stackDepth = 1024U * 8U,
        .priority = THREAD_PRIO_1,
        .thrdname = "gongzai_pendant",
    };

    tal_thread_create_and_start(
        &sg_app_thread,
        NULL,
        NULL,
        pendant_app_thread,
        NULL,
        &thread_cfg
    );
}
#endif
