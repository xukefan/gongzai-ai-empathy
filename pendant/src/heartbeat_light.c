#include "gongzai/heartbeat_light.h"

#include <stddef.h>

#define MIN_HEART_RATE_BPM 30U
#define MAX_HEART_RATE_BPM 240U
#define MAX_ATTACK_MS 40U
#define MAX_DECAY_MS 180U

static uint32_t min_u32(uint32_t left, uint32_t right)
{
    return left < right ? left : right;
}

void heartbeat_light_init(heartbeat_light_t *light)
{
    if (light == NULL) {
        return;
    }

    light->interval_ms = 0U;
    light->beat_started_ms = 0U;
    light->active = false;
}

uint32_t heartbeat_interval_ms(uint16_t bpm)
{
    if (bpm < MIN_HEART_RATE_BPM || bpm > MAX_HEART_RATE_BPM) {
        return 0U;
    }
    return 60000U / (uint32_t)bpm;
}

bool heartbeat_light_start(
    heartbeat_light_t *light,
    uint16_t bpm,
    uint32_t now_ms
)
{
    uint32_t interval_ms;

    if (light == NULL) {
        return false;
    }

    interval_ms = heartbeat_interval_ms(bpm);
    if (interval_ms == 0U) {
        heartbeat_light_stop(light);
        return false;
    }

    light->interval_ms = interval_ms;
    light->beat_started_ms = now_ms;
    light->active = true;
    return true;
}

void heartbeat_light_stop(heartbeat_light_t *light)
{
    if (light == NULL) {
        return;
    }

    light->interval_ms = 0U;
    light->active = false;
}

uint8_t heartbeat_light_level_at(
    const heartbeat_light_t *light,
    uint32_t now_ms
)
{
    uint32_t phase_ms;
    uint32_t attack_ms;
    uint32_t decay_ms;
    uint32_t pulse_ms;

    if (light == NULL || !light->active || light->interval_ms == 0U) {
        return 0U;
    }

    phase_ms = (now_ms - light->beat_started_ms) % light->interval_ms;
    attack_ms = min_u32(MAX_ATTACK_MS, light->interval_ms / 5U);
    if (attack_ms == 0U) {
        attack_ms = 1U;
    }

    decay_ms = min_u32(
        MAX_DECAY_MS,
        (light->interval_ms * 3U) / 5U
    );
    pulse_ms = attack_ms + decay_ms;

    if (phase_ms < attack_ms) {
        return (uint8_t)((phase_ms * 255U) / attack_ms);
    }
    if (phase_ms < pulse_ms && decay_ms > 0U) {
        return (uint8_t)(
            ((pulse_ms - phase_ms) * 255U) / decay_ms
        );
    }
    return 0U;
}
