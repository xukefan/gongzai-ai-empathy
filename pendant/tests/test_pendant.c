#include "gongzai/heartbeat_light.h"
#include "gongzai/pendant_controller.h"

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>

static uint32_t fake_now_ms;
static uint8_t fake_led_level;
static bool fake_audio_played;
static bool fake_recording_started;
static bool fake_recording_stopped;
static bool fake_recording_uploaded;
static pendant_state_t fake_reported_state;
static char fake_reported_event_id[GONGZAI_EVENT_ID_CAPACITY];

static void fake_set_led(uint8_t level)
{
    fake_led_level = level;
}

static bool fake_play_audio(const char *audio_ref)
{
    fake_audio_played = strcmp(audio_ref, "voice://moment-1") == 0;
    return fake_audio_played;
}

static bool fake_start_recording(const char *event_id)
{
    fake_recording_started = strcmp(event_id, "moment-1") == 0;
    return fake_recording_started;
}

static bool fake_stop_recording(char *path, size_t capacity)
{
    const char *value = "/tmp/reply.m4a";

    fake_recording_stopped = true;
    if (strlen(value) + 1U > capacity) {
        return false;
    }
    (void)strcpy(path, value);
    return true;
}

static bool fake_upload_recording(
    const char *event_id,
    const char *recording_path
)
{
    fake_recording_uploaded =
        strcmp(event_id, "moment-1") == 0 &&
        strcmp(recording_path, "/tmp/reply.m4a") == 0;
    return fake_recording_uploaded;
}

static void fake_report_state(
    const char *event_id,
    pendant_state_t state
)
{
    fake_reported_state = state;
    (void)strncpy(
        fake_reported_event_id,
        event_id,
        sizeof(fake_reported_event_id) - 1U
    );
    fake_reported_event_id[sizeof(fake_reported_event_id) - 1U] = '\0';
}

static uint32_t fake_now(void)
{
    return fake_now_ms;
}

static void reset_fakes(void)
{
    fake_now_ms = 0U;
    fake_led_level = 0U;
    fake_audio_played = false;
    fake_recording_started = false;
    fake_recording_stopped = false;
    fake_recording_uploaded = false;
    fake_reported_state = PENDANT_STATE_IDLE;
    fake_reported_event_id[0] = '\0';
}

static void test_heartbeat_light(void)
{
    heartbeat_light_t light;

    heartbeat_light_init(&light);
    assert(heartbeat_interval_ms(60U) == 1000U);
    assert(heartbeat_interval_ms(120U) == 500U);
    assert(heartbeat_interval_ms(10U) == 0U);
    assert(heartbeat_light_start(&light, 75U, 1000U));
    assert(light.interval_ms == 800U);
    assert(heartbeat_light_level_at(&light, 1020U) > 0U);
    assert(heartbeat_light_level_at(&light, 1300U) == 0U);
    assert(heartbeat_light_level_at(&light, 1820U) > 0U);

    heartbeat_light_stop(&light);
    assert(heartbeat_light_level_at(&light, 1900U) == 0U);
}

static void test_moment_and_reply_flow(void)
{
    pendant_controller_t controller;
    pendant_hal_t hal = {
        .set_led_brightness = fake_set_led,
        .play_audio = fake_play_audio,
        .start_recording = fake_start_recording,
        .stop_recording = fake_stop_recording,
        .upload_recording = fake_upload_recording,
        .report_state = fake_report_state,
        .now_ms = fake_now
    };

    reset_fakes();
    assert(pendant_controller_init(&controller, &hal));
    assert(controller.state == PENDANT_STATE_IDLE);

    assert(pendant_controller_receive_moment(
        &controller,
        "moment-1",
        80U,
        5000U,
        "voice://moment-1"
    ));
    assert(fake_audio_played);
    assert(controller.state == PENDANT_STATE_PLAYING);
    assert(strcmp(fake_reported_event_id, "moment-1") == 0);

    fake_now_ms = 20U;
    pendant_controller_tick(&controller);
    assert(fake_led_level > 0U);

    pendant_controller_on_audio_finished(&controller);
    assert(controller.state == PENDANT_STATE_INCOMING);

    pendant_controller_on_touch(&controller);
    assert(controller.state == PENDANT_STATE_ACKNOWLEDGED);

    assert(pendant_controller_on_record_button_pressed(&controller));
    assert(fake_recording_started);
    assert(controller.state == PENDANT_STATE_RECORDING);

    assert(pendant_controller_on_record_button_released(&controller));
    assert(fake_recording_stopped);
    assert(fake_recording_uploaded);
    assert(controller.state == PENDANT_STATE_UPLOADING);

    pendant_controller_on_upload_finished(&controller, true);
    assert(controller.state == PENDANT_STATE_REPLIED);

    fake_now_ms = 5000U;
    pendant_controller_tick(&controller);
    assert(fake_led_level == 0U);
}

int main(void)
{
    test_heartbeat_light();
    test_moment_and_reply_flow();
    puts("pendant_core_tests: ok");
    return 0;
}
