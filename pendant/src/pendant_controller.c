#include "gongzai/pendant_controller.h"

#include <string.h>

static void copy_text(char *destination, size_t capacity, const char *source)
{
    if (destination == NULL || capacity == 0U) {
        return;
    }

    if (source == NULL) {
        destination[0] = '\0';
        return;
    }

    (void)strncpy(destination, source, capacity - 1U);
    destination[capacity - 1U] = '\0';
}

static bool time_reached(uint32_t now_ms, uint32_t deadline_ms)
{
    return (int32_t)(now_ms - deadline_ms) >= 0;
}

static void report_state(pendant_controller_t *controller)
{
    if (controller->hal.report_state != NULL) {
        controller->hal.report_state(
            controller->event_id,
            controller->state
        );
    }
}

static void set_state(
    pendant_controller_t *controller,
    pendant_state_t state
)
{
    controller->state = state;
    report_state(controller);
}

bool pendant_controller_init(
    pendant_controller_t *controller,
    const pendant_hal_t *hal
)
{
    if (controller == NULL || hal == NULL ||
        hal->set_led_brightness == NULL || hal->now_ms == NULL) {
        return false;
    }

    (void)memset(controller, 0, sizeof(*controller));
    controller->hal = *hal;
    controller->state = PENDANT_STATE_IDLE;
    heartbeat_light_init(&controller->heartbeat_light);
    controller->hal.set_led_brightness(0U);
    return true;
}

bool pendant_controller_receive_moment(
    pendant_controller_t *controller,
    const char *event_id,
    uint16_t bpm,
    uint32_t heartbeat_duration_ms,
    const char *audio_ref
)
{
    uint32_t now_ms;

    if (controller == NULL || event_id == NULL || event_id[0] == '\0') {
        return false;
    }

    now_ms = controller->hal.now_ms();
    if (!heartbeat_light_start(
            &controller->heartbeat_light,
            bpm,
            now_ms
        )) {
        set_state(controller, PENDANT_STATE_ERROR);
        return false;
    }

    copy_text(
        controller->event_id,
        sizeof(controller->event_id),
        event_id
    );
    copy_text(
        controller->audio_ref,
        sizeof(controller->audio_ref),
        audio_ref
    );
    controller->heartbeat_deadline_ms = now_ms + heartbeat_duration_ms;
    controller->has_active_event = true;
    set_state(controller, PENDANT_STATE_INCOMING);

    if (controller->audio_ref[0] != '\0' &&
        controller->hal.play_audio != NULL) {
        if (!controller->hal.play_audio(controller->audio_ref)) {
            set_state(controller, PENDANT_STATE_ERROR);
            return false;
        }
        set_state(controller, PENDANT_STATE_PLAYING);
    }

    return true;
}

void pendant_controller_tick(pendant_controller_t *controller)
{
    uint32_t now_ms;
    uint8_t level;

    if (controller == NULL) {
        return;
    }

    now_ms = controller->hal.now_ms();
    if (controller->heartbeat_light.active &&
        time_reached(now_ms, controller->heartbeat_deadline_ms)) {
        heartbeat_light_stop(&controller->heartbeat_light);
    }

    level = heartbeat_light_level_at(
        &controller->heartbeat_light,
        now_ms
    );
    controller->hal.set_led_brightness(level);
}

void pendant_controller_on_audio_finished(pendant_controller_t *controller)
{
    if (controller == NULL ||
        controller->state != PENDANT_STATE_PLAYING) {
        return;
    }
    set_state(controller, PENDANT_STATE_INCOMING);
}

void pendant_controller_on_touch(pendant_controller_t *controller)
{
    if (controller == NULL || !controller->has_active_event) {
        return;
    }
    set_state(controller, PENDANT_STATE_ACKNOWLEDGED);
}

bool pendant_controller_on_record_button_pressed(
    pendant_controller_t *controller
)
{
    if (controller == NULL || !controller->has_active_event ||
        controller->state == PENDANT_STATE_RECORDING ||
        controller->hal.start_recording == NULL) {
        return false;
    }

    if (!controller->hal.start_recording(controller->event_id)) {
        set_state(controller, PENDANT_STATE_ERROR);
        return false;
    }

    set_state(controller, PENDANT_STATE_RECORDING);
    return true;
}

bool pendant_controller_on_record_button_released(
    pendant_controller_t *controller
)
{
    if (controller == NULL ||
        controller->state != PENDANT_STATE_RECORDING ||
        controller->hal.stop_recording == NULL ||
        controller->hal.upload_recording == NULL) {
        return false;
    }

    controller->recording_path[0] = '\0';
    if (!controller->hal.stop_recording(
            controller->recording_path,
            sizeof(controller->recording_path)
        ) || controller->recording_path[0] == '\0') {
        set_state(controller, PENDANT_STATE_ERROR);
        return false;
    }

    if (!controller->hal.upload_recording(
            controller->event_id,
            controller->recording_path
        )) {
        set_state(controller, PENDANT_STATE_ERROR);
        return false;
    }

    set_state(controller, PENDANT_STATE_UPLOADING);
    return true;
}

void pendant_controller_on_upload_finished(
    pendant_controller_t *controller,
    bool succeeded
)
{
    if (controller == NULL ||
        controller->state != PENDANT_STATE_UPLOADING) {
        return;
    }
    set_state(
        controller,
        succeeded ? PENDANT_STATE_REPLIED : PENDANT_STATE_ERROR
    );
}
