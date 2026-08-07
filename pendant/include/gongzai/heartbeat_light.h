#ifndef GONGZAI_HEARTBEAT_LIGHT_H
#define GONGZAI_HEARTBEAT_LIGHT_H

#include <stdbool.h>
#include <stdint.h>

typedef struct {
    uint32_t interval_ms;
    uint32_t beat_started_ms;
    bool active;
} heartbeat_light_t;

void heartbeat_light_init(heartbeat_light_t *light);

bool heartbeat_light_start(
    heartbeat_light_t *light,
    uint16_t bpm,
    uint32_t now_ms
);

void heartbeat_light_stop(heartbeat_light_t *light);

uint8_t heartbeat_light_level_at(
    const heartbeat_light_t *light,
    uint32_t now_ms
);

uint32_t heartbeat_interval_ms(uint16_t bpm);

#endif
