#ifndef GONGZAI_PENDANT_HTTP_BRIDGE_H
#define GONGZAI_PENDANT_HTTP_BRIDGE_H

#include <stdbool.h>
#include <stdint.h>

#define GONGZAI_HTTP_EVENT_ID_CAPACITY 64U
#define GONGZAI_HTTP_AUDIO_REF_CAPACITY 256U

typedef struct {
    uint16_t bpm;
    char event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY];
    char audio_ref[GONGZAI_HTTP_AUDIO_REF_CAPACITY];
} pendant_http_moment_t;

bool pendant_http_bridge_start(void);
bool pendant_http_bridge_take_moment(pendant_http_moment_t *moment);
void pendant_http_bridge_ack(const char *event_id, const char *status);
void pendant_http_bridge_respond(const char *event_id, const char *response_type);

#endif
