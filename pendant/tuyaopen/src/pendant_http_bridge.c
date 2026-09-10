/** Direct Wi-Fi bridge from the T5AI pendant to the Gongzai FastAPI server. */

#include "pendant_http_bridge.h"

#include "http_client_interface.h"
#include "netconn_wifi.h"
#include "netmgr.h"
#include "tal_api.h"
#include "tuya_config.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HTTP_TIMEOUT_MS 5000U
#define HTTP_POLL_MS    2500U
#define MULTIPART_BOUNDARY "----gongzaiT5AIReply"

static THREAD_HANDLE sg_http_thread = NULL;
static MUTEX_HANDLE sg_bridge_mutex = NULL;
static bool sg_pending_moment = false;
static bool sg_event_in_flight = false;
static bool sg_ack_pending = false;
static pendant_http_moment_t sg_moment;
static char sg_active_event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
static char sg_ack_event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
static char sg_ack_status[16] = {0};
/* Network I/O must stay on the bridge worker.  In particular, doing a POST
 * with a multi-kilobyte WAV inside an LVGL input callback is unreliable on
 * T5AI and can fail before a TCP request reaches FastAPI. */
static bool sg_voice_upload_pending = false;
static bool sg_voice_upload_running = false;
static bool sg_voice_upload_result_ready = false;
static bool sg_voice_upload_succeeded = false;
static char sg_voice_upload_event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
static const uint8_t *sg_voice_upload_data = NULL;
static uint32_t sg_voice_upload_size = 0U;
static uint32_t sg_voice_upload_duration_ms = 0U;

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

static bool bridge_lock(void)
{
    return sg_bridge_mutex != NULL && tal_mutex_lock(sg_bridge_mutex) == OPRT_OK;
}

static void bridge_unlock(void)
{
    if (sg_bridge_mutex != NULL) {
        (void)tal_mutex_unlock(sg_bridge_mutex);
    }
}

static bool network_is_up(void)
{
    netmgr_status_e status = NETMGR_LINK_DOWN;
    (void)netmgr_conn_get(NETCONN_AUTO, NETCONN_CMD_STATUS, &status);
    return status != NETMGR_LINK_DOWN;
}

static const char *json_string_value(const char *json, const char *key, char *out, size_t capacity)
{
    char needle[48];
    const char *start;
    const char *end;
    size_t length;

    (void)snprintf(needle, sizeof(needle), "\"%s\":\"", key);
    start = strstr(json, needle);
    if (start == NULL) {
        (void)snprintf(needle, sizeof(needle), "\"%s\": \"", key);
        start = strstr(json, needle);
    }
    if (start == NULL) {
        return NULL;
    }
    start += strlen(needle);
    end = strchr(start, '"');
    if (end == NULL) {
        return NULL;
    }
    length = (size_t)(end - start);
    if (length >= capacity) {
        PR_WARN("JSON field %s exceeds pendant buffer", key);
        return NULL;
    }
    memcpy(out, start, length);
    out[length] = '\0';
    return out;
}

static int json_int_value(const char *json, const char *key, int fallback)
{
    char needle[40];
    const char *value;
    (void)snprintf(needle, sizeof(needle), "\"%s\":", key);
    value = strstr(json, needle);
    if (value == NULL) {
        return fallback;
    }
    return atoi(value + strlen(needle));
}

/*
 * The current FastAPI development endpoint returns a relative voice path,
 * while a production server may return a complete signed URL.  The T5 player
 * needs a full URL in both cases, so normalize only the safe, expected forms.
 */
static bool normalize_audio_url(const char *value, char *out, size_t capacity)
{
    int written;

    if (out == NULL || capacity == 0U || value == NULL || value[0] == '\0') {
        return false;
    }

    if (strncmp(value, "http://", 7U) == 0 ||
        strncmp(value, "https://", 8U) == 0) {
        if (strlen(value) >= capacity) {
            PR_WARN("Audio URL is too long for pendant buffer");
            return false;
        }
        copy_text(out, capacity, value);
        return true;
    }

    if (value[0] != '/') {
        PR_WARN("Ignoring unsupported audio URL value");
        return false;
    }

    written = snprintf(
        out,
        capacity,
        "http://%s:%u%s",
        GONGZAI_API_HOST,
        (unsigned int)GONGZAI_API_PORT,
        value
    );
    if (written < 0 || (size_t)written >= capacity) {
        out[0] = '\0';
        PR_WARN("Expanded audio URL is too long for pendant buffer");
        return false;
    }
    return true;
}

static bool http_request_json(const char *method, const char *path, const char *body, char **response_body)
{
    http_client_response_t response = {0};
    http_client_header_t headers[2] = {
        {.key = "Content-Type", .value = "application/json"},
        {.key = "X-Pendant-Token", .value = GONGZAI_PENDANT_API_TOKEN},
    };
    uint8_t header_count = GONGZAI_PENDANT_API_TOKEN[0] == '\0' ? 1U : 2U;
    http_client_status_t result = http_client_request(
        &(const http_client_request_t){
            .host = GONGZAI_API_HOST,
            .port = GONGZAI_API_PORT,
            .method = method,
            .path = path,
            .headers = headers,
            .headers_count = header_count,
            .body = (const uint8_t *)(body != NULL ? body : ""),
            .body_length = body != NULL ? strlen(body) : 0U,
            .timeout_ms = HTTP_TIMEOUT_MS,
        },
        &response
    );
    bool ok = result == HTTP_CLIENT_SUCCESS && response.status_code >= 200U && response.status_code < 300U;

    if (ok) {
        PR_NOTICE("Pendant HTTP %s %s -> %u, %u bytes", method, path,
                  response.status_code, (unsigned int)response.body_length);
    }
    if (ok && response_body != NULL) {
        *response_body = tal_malloc(response.body_length + 1U);
        if (*response_body == NULL) {
            ok = false;
        } else {
            memcpy(*response_body, response.body, response.body_length);
            (*response_body)[response.body_length] = '\0';
        }
    }
    if (!ok) {
        PR_WARN("Pendant HTTP %s %s failed: client=%d status=%u", method, path, result, response.status_code);
    }
    http_client_free(&response);
    return ok;
}

static bool bridge_is_ready_to_poll(void)
{
    bool ready = false;

    if (!bridge_lock()) {
        return false;
    }
    ready = !sg_pending_moment && !sg_event_in_flight && !sg_ack_pending;
    bridge_unlock();
    return ready;
}

static void poll_once(void)
{
    char path[192];
    char *json = NULL;
    char event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
    char audio_url[GONGZAI_HTTP_AUDIO_REF_CAPACITY] = {0};
    int bpm;

    (void)snprintf(path, sizeof(path), "/api/pendant/events/next?device_id=%s", GONGZAI_PENDANT_DEVICE_ID);
    if (!http_request_json("GET", path, NULL, &json)) {
        return;
    }
    if (strstr(json, "\"status\":\"empty\"") != NULL ||
        json_string_value(json, "event_id", event_id, sizeof(event_id)) == NULL) {
        PR_DEBUG("No direct pendant event: %s", json);
        tal_free(json);
        return;
    }
    bpm = json_int_value(json, "bpm", 80);
    if (bpm < 30) bpm = 30;
    if (bpm > 240) bpm = 240;

    if (bridge_lock()) {
        if (!sg_pending_moment && !sg_event_in_flight) {
            (void)memset(&sg_moment, 0, sizeof(sg_moment));
            sg_moment.bpm = (uint16_t)bpm;
            copy_text(sg_moment.event_id, sizeof(sg_moment.event_id), event_id);
            if (json_string_value(json, "audio_url", audio_url, sizeof(audio_url)) != NULL) {
                if (!normalize_audio_url(
                        audio_url,
                        sg_moment.audio_ref,
                        sizeof(sg_moment.audio_ref)
                    )) {
                    PR_WARN("Event %s has no playable audio URL", event_id);
                }
            }
            sg_pending_moment = true;
            PR_NOTICE(
                "FastAPI event received: %s, %d BPM%s",
                event_id,
                bpm,
                sg_moment.audio_ref[0] != '\0' ? ", with original voice" : ""
            );
        }
        bridge_unlock();
    }
    tal_free(json);
}

static bool post_event_state(const char *event_id, const char *suffix, const char *json)
{
    char path[192];
    if (event_id == NULL || event_id[0] == '\0' || !network_is_up()) return false;
    (void)snprintf(path, sizeof(path), "/api/pendant/events/%s/%s", event_id, suffix);
    return http_request_json("POST", path, json, NULL);
}

/* Only the HTTP worker makes network calls.  UI and player callbacks merely
 * queue acknowledgements, which keeps LVGL responsive during audio playback. */
static void post_queued_ack(void)
{
    char event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
    char status[sizeof(sg_ack_status)] = {0};
    char body[192];

    if (!bridge_lock()) {
        return;
    }
    if (!sg_ack_pending) {
        bridge_unlock();
        return;
    }
    copy_text(event_id, sizeof(event_id), sg_ack_event_id);
    copy_text(status, sizeof(status), sg_ack_status);
    bridge_unlock();

    (void)snprintf(
        body,
        sizeof(body),
        "{\"device_id\":\"%s\",\"status\":\"%s\"}",
        GONGZAI_PENDANT_DEVICE_ID,
        status[0] != '\0' ? status : "played"
    );
    if (!post_event_state(event_id, "ack", body)) {
        return;
    }

    if (bridge_lock()) {
        /* Do not erase a newer acknowledgement queued while this request ran. */
        if (sg_ack_pending && strcmp(sg_ack_event_id, event_id) == 0) {
            sg_ack_pending = false;
            sg_ack_event_id[0] = '\0';
            sg_ack_status[0] = '\0';
        }
        if (strcmp(sg_active_event_id, event_id) == 0) {
            sg_event_in_flight = false;
            sg_active_event_id[0] = '\0';
        }
        bridge_unlock();
    }
    PR_NOTICE("Pendant playback ACK delivered: %s", event_id);
}

static bool upload_voice_reply_now(
    const char *event_id,
    const uint8_t *wav_data,
    uint32_t wav_size,
    uint32_t duration_ms
)
{
    char path[256];
    char prefix[384];
    static const char suffix[] = "\r\n--" MULTIPART_BOUNDARY "--\r\n";
    http_client_response_t response = {0};
    http_client_header_t headers[2];
    char content_type[96];
    uint8_t *body;
    size_t prefix_size;
    size_t body_size;
    http_client_status_t result;
    bool ok;

    if (event_id == NULL || event_id[0] == '\0' || wav_data == NULL ||
        wav_size <= 44U || !network_is_up()) {
        return false;
    }
    (void)snprintf(
        path, sizeof(path),
        "/api/pendant/voice/upload?device_id=%s&event_id=%s&duration_ms=%u",
        GONGZAI_PENDANT_DEVICE_ID, event_id, (unsigned int)duration_ms
    );
    (void)snprintf(
        prefix, sizeof(prefix),
        "--%s\r\n"
        "Content-Disposition: form-data; name=\"file\"; filename=\"reply.wav\"\r\n"
        "Content-Type: audio/wav\r\n\r\n",
        MULTIPART_BOUNDARY
    );
    (void)snprintf(content_type, sizeof(content_type),
                   "multipart/form-data; boundary=%s", MULTIPART_BOUNDARY);
    prefix_size = strlen(prefix);
    body_size = prefix_size + (size_t)wav_size + sizeof(suffix) - 1U;
    body = tal_psram_malloc(body_size);
    if (body == NULL) {
        PR_ERR("Unable to allocate reply upload body: %u bytes", (unsigned int)body_size);
        return false;
    }
    memcpy(body, prefix, prefix_size);
    memcpy(body + prefix_size, wav_data, wav_size);
    memcpy(body + prefix_size + wav_size, suffix, sizeof(suffix) - 1U);

    headers[0] = (http_client_header_t){.key = "Content-Type", .value = content_type};
    headers[1] = (http_client_header_t){.key = "X-Pendant-Token", .value = GONGZAI_PENDANT_API_TOKEN};
    result = http_client_request(
        &(const http_client_request_t){
            .host = GONGZAI_API_HOST, .port = GONGZAI_API_PORT,
            .method = "POST", .path = path, .headers = headers,
            .headers_count = GONGZAI_PENDANT_API_TOKEN[0] == '\0' ? 1U : 2U,
            .body = body, .body_length = body_size,
            .timeout_ms = HTTP_TIMEOUT_MS,
        }, &response
    );
    ok = result == HTTP_CLIENT_SUCCESS && response.status_code >= 200U && response.status_code < 300U;
    if (ok) {
        PR_NOTICE("Pendant voice reply uploaded: event=%s bytes=%u", event_id, wav_size);
    } else {
        PR_ERR("Pendant voice reply upload failed: event=%s client=%d status=%u",
               event_id, result, response.status_code);
    }
    http_client_free(&response);
    tal_psram_free(body);
    return ok;
}

static void post_queued_voice_upload(void)
{
    char event_id[GONGZAI_HTTP_EVENT_ID_CAPACITY] = {0};
    const uint8_t *wav_data = NULL;
    uint32_t wav_size = 0U;
    uint32_t duration_ms = 0U;
    bool succeeded;

    if (!bridge_lock()) return;
    if (!sg_voice_upload_pending || sg_voice_upload_running) {
        bridge_unlock();
        return;
    }
    copy_text(event_id, sizeof(event_id), sg_voice_upload_event_id);
    wav_data = sg_voice_upload_data;
    wav_size = sg_voice_upload_size;
    duration_ms = sg_voice_upload_duration_ms;
    sg_voice_upload_pending = false;
    sg_voice_upload_running = true;
    bridge_unlock();

    succeeded = upload_voice_reply_now(event_id, wav_data, wav_size, duration_ms);

    if (bridge_lock()) {
        sg_voice_upload_running = false;
        sg_voice_upload_succeeded = succeeded;
        sg_voice_upload_result_ready = true;
        sg_voice_upload_data = NULL;
        sg_voice_upload_size = 0U;
        sg_voice_upload_duration_ms = 0U;
        bridge_unlock();
    }
}

static void http_worker(void *arg)
{
    (void)arg;
    for (;;) {
        if (network_is_up()) {
            post_queued_voice_upload();
            post_queued_ack();
            if (bridge_is_ready_to_poll()) {
                poll_once();
            }
        }
        tal_system_sleep(HTTP_POLL_MS);
    }
}

bool pendant_http_bridge_start(void)
{
    THREAD_CFG_T cfg = {
        .stackDepth = 1024U * 6U,
        .priority = THREAD_PRIO_3,
        .thrdname = "gongzai_http",
    };
    if (sg_bridge_mutex == NULL && tal_mutex_create_init(&sg_bridge_mutex) != OPRT_OK) {
        PR_ERR("Unable to create FastAPI bridge mutex");
        return false;
    }
    return sg_http_thread != NULL || tal_thread_create_and_start(
        &sg_http_thread, NULL, NULL, http_worker, NULL, &cfg
    ) == OPRT_OK;
}

bool pendant_http_bridge_take_moment(pendant_http_moment_t *moment)
{
    if (moment == NULL || !bridge_lock()) return false;
    if (!sg_pending_moment) {
        bridge_unlock();
        return false;
    }
    *moment = sg_moment;
    copy_text(sg_active_event_id, sizeof(sg_active_event_id), moment->event_id);
    sg_event_in_flight = true;
    sg_pending_moment = false;
    bridge_unlock();
    return true;
}

void pendant_http_bridge_ack(const char *event_id, const char *status)
{
    if (event_id == NULL || event_id[0] == '\0' || !bridge_lock()) {
        return;
    }
    copy_text(sg_ack_event_id, sizeof(sg_ack_event_id), event_id);
    copy_text(sg_ack_status, sizeof(sg_ack_status), status != NULL ? status : "played");
    sg_ack_pending = true;
    bridge_unlock();
    PR_NOTICE("Pendant playback ACK queued: %s", event_id);
}

void pendant_http_bridge_retry_event(const char *event_id)
{
    if (event_id == NULL || event_id[0] == '\0' || !bridge_lock()) {
        return;
    }
    if (strcmp(sg_active_event_id, event_id) == 0 && !sg_ack_pending) {
        sg_event_in_flight = false;
        sg_active_event_id[0] = '\0';
        PR_WARN("Pendant event released for retry: %s", event_id);
    }
    bridge_unlock();
}

void pendant_http_bridge_respond(const char *event_id, const char *response_type)
{
    char body[256];
    (void)snprintf(body, sizeof(body),
                   "{\"device_id\":\"%s\",\"event_id\":\"%s\",\"response_type\":\"%s\"}",
                   GONGZAI_PENDANT_DEVICE_ID, event_id,
                   response_type != NULL ? response_type : "touch");
    (void)http_request_json("POST", "/api/pendant/responses", body, NULL);
}

bool pendant_http_bridge_upload_voice_reply(
    const char *event_id,
    const uint8_t *wav_data,
    uint32_t wav_size,
    uint32_t duration_ms
)
{
    if (event_id == NULL || event_id[0] == '\0' || wav_data == NULL ||
        wav_size <= 44U || !network_is_up() || !bridge_lock()) {
        return false;
    }
    if (sg_voice_upload_pending || sg_voice_upload_running) {
        bridge_unlock();
        PR_WARN("Voice upload is already queued");
        return false;
    }
    copy_text(sg_voice_upload_event_id, sizeof(sg_voice_upload_event_id), event_id);
    sg_voice_upload_data = wav_data;
    sg_voice_upload_size = wav_size;
    sg_voice_upload_duration_ms = duration_ms;
    sg_voice_upload_pending = true;
    sg_voice_upload_result_ready = false;
    bridge_unlock();
    PR_NOTICE("Pendant voice reply queued: event=%s bytes=%u", event_id, wav_size);
    return true;
}

bool pendant_http_bridge_take_voice_upload_result(bool *succeeded)
{
    if (succeeded == NULL || !bridge_lock()) return false;
    if (!sg_voice_upload_result_ready) {
        bridge_unlock();
        return false;
    }
    *succeeded = sg_voice_upload_succeeded;
    sg_voice_upload_result_ready = false;
    bridge_unlock();
    return true;
}
