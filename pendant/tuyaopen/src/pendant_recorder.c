/**
 * @file pendant_recorder.c
 * @brief T5AI microphone capture and in-memory PCM WAV packaging.
 */

#include "pendant_recorder.h"

#include "tal_api.h"
#include "tuya_ringbuf.h"

#include <limits.h>
#include <stddef.h>
#include <string.h>

#define WAV_HEADER_SIZE 44U

typedef struct {
    TDL_AUDIO_HANDLE_T audio_handle;
    TDL_AUDIO_INFO_T audio_info;
    TUYA_RINGBUFF_T pcm_ring_buffer;
    uint8_t *wav_data;
    uint32_t wav_size;
    uint32_t duration_ms;
    uint32_t captured_frames;
    uint32_t dropped_frames;
    uint16_t peak_amplitude;
    volatile bool recording;
    volatile bool overflow_reported;
    bool ready;
} pendant_recorder_context_t;

static pendant_recorder_context_t sg_recorder;

static void write_le16(uint8_t *destination, uint16_t value)
{
    destination[0] = (uint8_t)(value & 0xFFU);
    destination[1] = (uint8_t)((value >> 8U) & 0xFFU);
}

static void write_le32(uint8_t *destination, uint32_t value)
{
    destination[0] = (uint8_t)(value & 0xFFU);
    destination[1] = (uint8_t)((value >> 8U) & 0xFFU);
    destination[2] = (uint8_t)((value >> 16U) & 0xFFU);
    destination[3] = (uint8_t)((value >> 24U) & 0xFFU);
}

static void write_wav_header(
    uint8_t *destination,
    const TDL_AUDIO_INFO_T *audio_info,
    uint32_t pcm_size
)
{
    uint16_t block_align = (uint16_t)(
        audio_info->sample_ch_num * (audio_info->sample_bits / 8U)
    );
    uint32_t byte_rate =
        (uint32_t)audio_info->sample_rate * (uint32_t)block_align;

    (void)memcpy(&destination[0], "RIFF", 4U);
    write_le32(&destination[4], 36U + pcm_size);
    (void)memcpy(&destination[8], "WAVE", 4U);
    (void)memcpy(&destination[12], "fmt ", 4U);
    write_le32(&destination[16], 16U);
    write_le16(&destination[20], 1U);
    write_le16(&destination[22], audio_info->sample_ch_num);
    write_le32(&destination[24], audio_info->sample_rate);
    write_le32(&destination[28], byte_rate);
    write_le16(&destination[32], block_align);
    write_le16(&destination[34], audio_info->sample_bits);
    (void)memcpy(&destination[36], "data", 4U);
    write_le32(&destination[40], pcm_size);
}

static uint16_t calculate_pcm_peak(
    const uint8_t *pcm_data,
    uint32_t pcm_size,
    uint16_t sample_bits
)
{
    uint32_t index;
    uint16_t peak = 0U;

    if (pcm_data == NULL || sample_bits != 16U) {
        return 0U;
    }

    for (index = 0U; index + 1U < pcm_size; index += 2U) {
        int16_t sample = (int16_t)(
            (uint16_t)pcm_data[index] |
            ((uint16_t)pcm_data[index + 1U] << 8U)
        );
        uint16_t amplitude = sample == INT16_MIN
            ? (uint16_t)INT16_MAX + 1U
            : (uint16_t)(sample < 0 ? -sample : sample);

        if (amplitude > peak) {
            peak = amplitude;
        }
    }

    return peak;
}

static void release_wav_asset(void)
{
    if (sg_recorder.wav_data != NULL) {
        tal_psram_free(sg_recorder.wav_data);
        sg_recorder.wav_data = NULL;
    }

    sg_recorder.wav_size = 0U;
    sg_recorder.duration_ms = 0U;
    sg_recorder.peak_amplitude = 0U;
}

static void microphone_frame_callback(
    TDL_AUDIO_FRAME_FORMAT_E type,
    TDL_AUDIO_STATUS_E status,
    uint8_t *data,
    uint32_t len
)
{
    uint32_t free_size;
    uint32_t written;

    (void)status;

    if (!sg_recorder.recording ||
        type != TDL_AUDIO_FRAME_FORMAT_PCM ||
        data == NULL || len == 0U ||
        sg_recorder.pcm_ring_buffer == NULL) {
        return;
    }

    free_size = tuya_ring_buff_free_size_get(sg_recorder.pcm_ring_buffer);
    if (free_size < len) {
        sg_recorder.dropped_frames++;
        if (!sg_recorder.overflow_reported) {
            sg_recorder.overflow_reported = true;
            PR_WARN(
                "Reply recording reached the %u ms limit; extra frames are ignored",
                PENDANT_RECORDER_MAX_DURATION_MS
            );
        }
        return;
    }

    written = tuya_ring_buff_write(
        sg_recorder.pcm_ring_buffer,
        data,
        len
    );
    if (written == len) {
        sg_recorder.captured_frames++;
    } else {
        sg_recorder.dropped_frames++;
    }
}

OPERATE_RET pendant_recorder_open(TDL_AUDIO_HANDLE_T audio_handle)
{
    OPERATE_RET rt;
    uint32_t frame_count;
    uint32_t buffer_size;

    if (audio_handle == NULL) {
        return OPRT_INVALID_PARM;
    }

    (void)memset(&sg_recorder, 0, sizeof(sg_recorder));
    sg_recorder.audio_handle = audio_handle;

    TUYA_CALL_ERR_RETURN(tdl_audio_open(
        sg_recorder.audio_handle,
        microphone_frame_callback
    ));
    TUYA_CALL_ERR_RETURN(tdl_audio_get_info(
        sg_recorder.audio_handle,
        &sg_recorder.audio_info
    ));

    if (sg_recorder.audio_info.frame_size == 0U ||
        sg_recorder.audio_info.sample_tm_ms == 0U ||
        sg_recorder.audio_info.sample_rate == 0U ||
        sg_recorder.audio_info.sample_ch_num == 0U ||
        sg_recorder.audio_info.sample_bits == 0U) {
        PR_ERR("Invalid T5AI microphone format");
        return OPRT_INVALID_PARM;
    }

    frame_count =
        PENDANT_RECORDER_MAX_DURATION_MS /
        sg_recorder.audio_info.sample_tm_ms;
    buffer_size = frame_count * sg_recorder.audio_info.frame_size;
    rt = tuya_ring_buff_create(
        buffer_size,
        OVERFLOW_PSRAM_STOP_TYPE,
        &sg_recorder.pcm_ring_buffer
    );
    if (rt != OPRT_OK) {
        PR_ERR("Unable to allocate microphone ring buffer: %d", rt);
        return rt;
    }

    sg_recorder.ready = true;
    PR_NOTICE(
        "T5AI microphone ready: %u Hz, %u-bit, %u channel(s), frame=%u bytes, capacity=%u bytes",
        sg_recorder.audio_info.sample_rate,
        sg_recorder.audio_info.sample_bits,
        sg_recorder.audio_info.sample_ch_num,
        sg_recorder.audio_info.frame_size,
        buffer_size
    );
    return OPRT_OK;
}

bool pendant_recorder_start(void)
{
    if (!sg_recorder.ready ||
        sg_recorder.pcm_ring_buffer == NULL ||
        sg_recorder.recording) {
        return false;
    }

    release_wav_asset();
    if (tuya_ring_buff_reset(sg_recorder.pcm_ring_buffer) != OPRT_OK) {
        return false;
    }

    sg_recorder.captured_frames = 0U;
    sg_recorder.dropped_frames = 0U;
    sg_recorder.overflow_reported = false;
    sg_recorder.recording = true;
    PR_NOTICE("T5AI microphone capture started");
    return true;
}

bool pendant_recorder_stop(void)
{
    uint32_t pcm_size;
    uint32_t read_size;
    uint32_t bytes_per_second;
    uint32_t wav_size;
    uint8_t *wav_data;

    if (!sg_recorder.ready || !sg_recorder.recording) {
        return false;
    }

    sg_recorder.recording = false;
    pcm_size = tuya_ring_buff_used_size_get(sg_recorder.pcm_ring_buffer);
    if (pcm_size == 0U || pcm_size > UINT32_MAX - WAV_HEADER_SIZE) {
        PR_ERR("T5AI microphone produced no usable PCM data");
        return false;
    }

    wav_size = WAV_HEADER_SIZE + pcm_size;
    wav_data = tal_psram_malloc(wav_size);
    if (wav_data == NULL) {
        PR_ERR("Unable to allocate %u-byte reply WAV asset", wav_size);
        return false;
    }

    write_wav_header(wav_data, &sg_recorder.audio_info, pcm_size);
    read_size = tuya_ring_buff_read(
        sg_recorder.pcm_ring_buffer,
        &wav_data[WAV_HEADER_SIZE],
        pcm_size
    );
    if (read_size != pcm_size) {
        PR_ERR(
            "Incomplete microphone read: expected=%u actual=%u",
            pcm_size,
            read_size
        );
        tal_psram_free(wav_data);
        return false;
    }

    bytes_per_second =
        (uint32_t)sg_recorder.audio_info.sample_rate *
        (uint32_t)sg_recorder.audio_info.sample_ch_num *
        ((uint32_t)sg_recorder.audio_info.sample_bits / 8U);

    sg_recorder.wav_data = wav_data;
    sg_recorder.wav_size = wav_size;
    sg_recorder.duration_ms = bytes_per_second == 0U
        ? 0U
        : (uint32_t)(((uint64_t)pcm_size * 1000ULL) / bytes_per_second);
    sg_recorder.peak_amplitude = calculate_pcm_peak(
        &wav_data[WAV_HEADER_SIZE],
        pcm_size,
        sg_recorder.audio_info.sample_bits
    );

    PR_NOTICE(
        "Reply WAV ready: bytes=%u duration=%u ms peak=%u frames=%u dropped=%u",
        sg_recorder.wav_size,
        sg_recorder.duration_ms,
        sg_recorder.peak_amplitude,
        sg_recorder.captured_frames,
        sg_recorder.dropped_frames
    );
    return true;
}

const uint8_t *pendant_recorder_wav_data(void)
{
    return sg_recorder.wav_data;
}

uint32_t pendant_recorder_wav_size(void)
{
    return sg_recorder.wav_size;
}

uint32_t pendant_recorder_duration_ms(void)
{
    return sg_recorder.duration_ms;
}

uint16_t pendant_recorder_peak_amplitude(void)
{
    return sg_recorder.peak_amplitude;
}

bool pendant_recorder_is_recording(void)
{
    return sg_recorder.recording;
}
