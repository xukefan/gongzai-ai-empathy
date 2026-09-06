/**
 * @file tuya_config.h
 * @brief Product configuration for the Gongzai Pendant.
 *
 * The actual Tuya OpenSDK UUID/AuthKey must never be committed. Put local
 * overrides in tuya_config_secrets.h (ignored by Git), or write the license
 * into the board with the Tuya authorization tool after flashing.
 */

#ifndef GONGZAI_TUYA_CONFIG_H
#define GONGZAI_TUYA_CONFIG_H

#if defined(__has_include)
#if __has_include("tuya_config_secrets.h")
#include "tuya_config_secrets.h"
#endif
#endif

#ifndef TUYA_PRODUCT_ID
#define TUYA_PRODUCT_ID "irvw50xfd7hcgyw7"
#endif

/* Placeholders are intentionally non-functional and contain no credentials. */
#ifndef TUYA_OPENSDK_UUID
#define TUYA_OPENSDK_UUID "uuid-not-installed"
#endif

#ifndef TUYA_OPENSDK_AUTHKEY
#define TUYA_OPENSDK_AUTHKEY "authkey-not-installed"
#endif

#endif /* GONGZAI_TUYA_CONFIG_H */
