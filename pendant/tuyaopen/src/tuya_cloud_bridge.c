/**
 * @file tuya_cloud_bridge.c
 * @brief Tuya cloud worker and the Gongzai Pendant DP bridge.
 */

#include "tuya_cloud_bridge.h"

#include "netmgr.h"
#include "netconn_wifi.h"
#include "tal_api.h"
#include "tuya_authorize.h"
#include "tuya_config.h"
#include "tuya_iot.h"
#include "tuya_iot_dp.h"

#include <stdio.h>
#include <string.h>

#define GONGZAI_DP_BPM       101U
#define GONGZAI_DP_PATTERN   102U
#define GONGZAI_DP_TRIGGER   103U
#define GONGZAI_DP_TOUCH_ACK 104U
#define GONGZAI_DEFAULT_BPM  80U

static tuya_iot_client_t sg_client;
static tuya_iot_license_t sg_license;
static THREAD_HANDLE sg_cloud_thread = NULL;
static volatile bool sg_cloud_ready = false;
static volatile bool sg_pending_touch = false;
static volatile bool sg_pending_moment = false;
static volatile uint16_t sg_pending_bpm = GONGZAI_DEFAULT_BPM;
static volatile uint32_t sg_event_sequence = 0U;
static char sg_pending_event_id[GONGZAI_CLOUD_EVENT_ID_CAPACITY];

static void queue_cloud_moment(uint16_t bpm)
{
    uint32_t sequence = ++sg_event_sequence;

    if (bpm < 30U) {
        bpm = 30U;
    } else if (bpm > 240U) {
        bpm = 240U;
    }

    sg_pending_bpm = bpm;
    (void)snprintf(
        sg_pending_event_id,
        sizeof(sg_pending_event_id),
        "cloud-%04lu",
        (unsigned long)sequence
    );
    sg_pending_moment = true;
    PR_NOTICE(
        "Cloud moment queued: event=%s bpm=%u",
        sg_pending_event_id,
        bpm
    );
}

static bool cloud_network_check(void)
{
    netmgr_status_e status = NETMGR_LINK_DOWN;

    (void)netmgr_conn_get(NETCONN_AUTO, NETCONN_CMD_STATUS, &status);
    return status != NETMGR_LINK_DOWN;
}

static void cloud_event_handler(
    tuya_iot_client_t *client,
    tuya_event_msg_t *event
)
{
    uint16_t index;
    dp_obj_recv_t *received;

    (void)client;
    if (event == NULL) {
        return;
    }

    PR_NOTICE(
        "Tuya event: %d (%s)",
        event->id,
        EVENT_ID2STR(event->id)
    );

    if (event->id == TUYA_EVENT_MQTT_CONNECTED) {
        sg_cloud_ready = true;
        PR_NOTICE("Tuya cloud connected");
        return;
    }

    if (event->id == TUYA_EVENT_MQTT_DISCONNECT) {
        sg_cloud_ready = false;
        PR_WARN("Tuya cloud disconnected");
        return;
    }

    if (event->id != TUYA_EVENT_DP_RECEIVE_OBJ ||
        event->value.dpobj == NULL) {
        return;
    }

    received = event->value.dpobj;
    for (index = 0U; index < received->dpscnt; index++) {
        dp_obj_t *dp = &received->dps[index];

        switch (dp->id) {
        case GONGZAI_DP_BPM:
            if (dp->type == PROP_VALUE) {
                queue_cloud_moment((uint16_t)dp->value.dp_value);
            }
            break;
        case GONGZAI_DP_TRIGGER:
            if (dp->type == PROP_BOOL && dp->value.dp_bool) {
                queue_cloud_moment(sg_pending_bpm);
            }
            break;
        case GONGZAI_DP_PATTERN:
            if (dp->type == PROP_STR && dp->value.dp_str != NULL) {
                PR_NOTICE("Cloud heartbeat pattern received: %s", dp->value.dp_str);
            }
            break;
        default:
            PR_DEBUG("Ignoring unsupported Gongzai DP id=%u", dp->id);
            break;
        }
    }
}

static void cloud_report_touch_ack(void)
{
    dp_obj_t dp = {
        .id = GONGZAI_DP_TOUCH_ACK,
        .type = PROP_ENUM,
        .value.dp_enum = 0U, /* tap */
        .time_stamp = 0U,
    };

    if (!sg_cloud_ready || sg_client.activate.devid[0] == '\0') {
        return;
    }

    (void)tuya_iot_dp_obj_report(
        &sg_client,
        sg_client.activate.devid,
        &dp,
        1U,
        0
    );
}

static void cloud_worker(void *arg)
{
    int rt;

    (void)arg;

    /* The KV store is needed by the authorization and network managers. */
    (void)tal_kv_init(&(tal_kv_cfg_t){
        .seed = "gongzai-kv-seed",
        .key = "gongzai-kv-key",
    });
    (void)tal_workq_init();
    (void)tal_cli_init();
    (void)tuya_authorize_init();

    if (tuya_authorize_read(&sg_license) != OPRT_OK) {
        sg_license.uuid = TUYA_OPENSDK_UUID;
        sg_license.authkey = TUYA_OPENSDK_AUTHKEY;
        PR_WARN(
            "Tuya license not found in device KV; write UUID/AuthKey before cloud use"
        );
    }

    rt = tuya_iot_init(&sg_client, &(const tuya_iot_config_t){
        .software_ver = PROJECT_VERSION,
        .productkey = TUYA_PRODUCT_ID,
        .uuid = sg_license.uuid,
        .authkey = sg_license.authkey,
        .event_handler = cloud_event_handler,
        .network_check = cloud_network_check,
    });
    if (rt != OPRT_OK) {
        PR_ERR("tuya_iot_init failed: %d", rt);
        return;
    }

    (void)netmgr_init(NETCONN_WIFI);
    (void)netmgr_conn_set(
        NETCONN_WIFI,
        NETCONN_CMD_NETCFG,
        &(netcfg_args_t){.type = NETCFG_TUYA_BLE | NETCFG_TUYA_WIFI_AP}
    );

    rt = tuya_iot_start(&sg_client);
    if (rt != OPRT_OK) {
        PR_ERR("tuya_iot_start failed: %d", rt);
        return;
    }

    PR_NOTICE("Gongzai Tuya cloud worker started");
    for (;;) {
        (void)tuya_iot_yield(&sg_client);
        if (sg_pending_touch) {
            sg_pending_touch = false;
            cloud_report_touch_ack();
        }
        tal_system_sleep(20U);
    }
}

bool tuya_cloud_bridge_start(void)
{
    THREAD_CFG_T thread_cfg = {
        .stackDepth = 1024U * 8U,
        .priority = THREAD_PRIO_2,
        .thrdname = "gongzai_tuya",
    };

    if (sg_cloud_thread != NULL) {
        return true;
    }

    return tal_thread_create_and_start(
        &sg_cloud_thread,
        NULL,
        NULL,
        cloud_worker,
        NULL,
        &thread_cfg
    ) == OPRT_OK;
}

bool tuya_cloud_bridge_take_moment(tuya_cloud_moment_t *moment)
{
    if (moment == NULL || !sg_pending_moment) {
        return false;
    }

    moment->bpm = sg_pending_bpm;
    (void)strncpy(
        moment->event_id,
        sg_pending_event_id,
        sizeof(moment->event_id) - 1U
    );
    moment->event_id[sizeof(moment->event_id) - 1U] = '\0';
    moment->valid = true;
    sg_pending_moment = false;
    return true;
}

void tuya_cloud_bridge_report_touch(void)
{
    sg_pending_touch = true;
}
