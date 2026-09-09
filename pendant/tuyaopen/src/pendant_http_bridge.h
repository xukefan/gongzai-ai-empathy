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
/* Queues the acknowledgement for the bridge worker; it does not make a
 * network request in the caller's UI or audio context. */
void pendant_http_bridge_ack(const char *event_id, const char *status);
/* Releases a locally claimed event without ACKing it, so a later poll can
 * retry it after a transient speaker or URL-start failure. */
void pendant_http_bridge_retry_event(const char *event_id);
void pendant_http_bridge_respond(const char *event_id, const char *response_type);
/* Upload an in-memory WAV reply using the pendant token.  Returns true only
 * after the server has persisted and associated it with the event. */
bool pendant_http_bridge_upload_voice_reply(
    const char *event_id,
    const uint8_t *wav_data,
    uint32_t wav_size,
    uint32_t duration_ms
);

#endif
