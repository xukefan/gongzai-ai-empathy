#ifndef GONGZAI_PENDANT_RECORDER_H
#define GONGZAI_PENDANT_RECORDER_H

#include "tuya_cloud_types.h"

#include "tdl_audio_manage.h"

#include <stdbool.h>
#include <stdint.h>

#define PENDANT_RECORDER_MAX_DURATION_MS (15U * 1000U)
#define PENDANT_RECORDER_WAV_URI "memory://gongzai-reply.wav"

/**
 * @brief Open the T5AI audio input and allocate the PCM capture buffer.
 *
 * The recorder owns the microphone callback registered for @p audio_handle.
 * The same audio handle may still be used by the player for speaker output.
 */
OPERATE_RET pendant_recorder_open(TDL_AUDIO_HANDLE_T audio_handle);

/** @brief Reset previous PCM data and begin capturing microphone frames. */
bool pendant_recorder_start(void);

/**
 * @brief Stop capture and package the recorded PCM into an in-memory WAV.
 *
 * The returned asset remains owned by the recorder and is replaced when the
 * next recording is stopped. Use the data/size accessors for a later HTTP
 * upload; no private voice data is written to local storage.
 */
bool pendant_recorder_stop(void);

/** @return The current upload-ready WAV bytes, or NULL when unavailable. */
const uint8_t *pendant_recorder_wav_data(void);

/** @return Size of the current upload-ready WAV asset in bytes. */
uint32_t pendant_recorder_wav_size(void);

/** @return Captured PCM duration represented by the current WAV asset. */
uint32_t pendant_recorder_duration_ms(void);

/** @return Maximum absolute 16-bit PCM sample found in the last recording. */
uint16_t pendant_recorder_peak_amplitude(void);

/** @return true while microphone frames are being appended. */
bool pendant_recorder_is_recording(void);

#endif
