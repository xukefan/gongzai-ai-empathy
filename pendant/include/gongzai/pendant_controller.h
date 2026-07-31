#ifndef GONGZAI_PENDANT_CONTROLLER_H
#define GONGZAI_PENDANT_CONTROLLER_H

#include "gongzai/heartbeat_light.h"

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

#define GONGZAI_EVENT_ID_CAPACITY 64U
#define GONGZAI_AUDIO_REF_CAPACITY 256U
#define GONGZAI_RECORDING_PATH_CAPACITY 256U

typedef enum {
    PENDANT_STATE_IDLE = 0,
    PENDANT_STATE_INCOMING,
    PENDANT_STATE_PLAYING,
    PENDANT_STATE_ACKNOWLEDGED,
    PENDANT_STATE_RECORDING,
    PENDANT_STATE_UPLOADING,
    PENDANT_STATE_REPLIED,
    PENDANT_STATE_ERROR
} pendant_state_t;

typedef struct {
    void (*set_led_brightness)(uint8_t level);
    bool (*play_audio)(const char *audio_ref);
    bool (*start_recording)(const char *event_id);
    bool (*stop_recording)(
        char *recording_path,
        size_t recording_path_capacity
    );
    bool (*upload_recording)(
        const char *event_id,
        const char *recording_path
    );
    void (*report_state)(
        const char *event_id,
        pendant_state_t state
    );
    uint32_t (*now_ms)(void);
} pendant_hal_t;

typedef struct {
    pendant_hal_t hal;
    heartbeat_light_t heartbeat_light;
    pendant_state_t state;
    char event_id[GONGZAI_EVENT_ID_CAPACITY];
    char audio_ref[GONGZAI_AUDIO_REF_CAPACITY];
    char recording_path[GONGZAI_RECORDING_PATH_CAPACITY];
    uint32_t heartbeat_deadline_ms;
    bool has_active_event;
} pendant_controller_t;

bool pendant_controller_init(
    pendant_controller_t *controller,
    const pendant_hal_t *hal
);

bool pendant_controller_receive_moment(
    pendant_controller_t *controller,
    const char *event_id,
    uint16_t bpm,
    uint32_t heartbeat_duration_ms,
    const char *audio_ref
);

void pendant_controller_tick(pendant_controller_t *controller);
void pendant_controller_on_audio_finished(pendant_controller_t *controller);
void pendant_controller_on_touch(pendant_controller_t *controller);
bool pendant_controller_on_record_button_pressed(
    pendant_controller_t *controller
);
bool pendant_controller_on_record_button_released(
    pendant_controller_t *controller
);
void pendant_controller_on_upload_finished(
    pendant_controller_t *controller,
    bool succeeded
);

#endif
