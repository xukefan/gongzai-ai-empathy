#ifndef GONGZAI_TUYA_CLOUD_BRIDGE_H
#define GONGZAI_TUYA_CLOUD_BRIDGE_H

#include <stdbool.h>
#include <stdint.h>

#define GONGZAI_CLOUD_EVENT_ID_CAPACITY 64U

typedef struct {
    bool valid;
    uint16_t bpm;
    char event_id[GONGZAI_CLOUD_EVENT_ID_CAPACITY];
} tuya_cloud_moment_t;

bool tuya_cloud_bridge_start(void);
bool tuya_cloud_bridge_take_moment(tuya_cloud_moment_t *moment);
void tuya_cloud_bridge_report_touch(void);

#endif /* GONGZAI_TUYA_CLOUD_BRIDGE_H */
