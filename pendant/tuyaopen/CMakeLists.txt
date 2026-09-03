##
# @file CMakeLists.txt
# @brief Gongzai T5AI pendant prototype.
#/

set(APP_PATH ${CMAKE_CURRENT_LIST_DIR})

file(GLOB APP_SRCS "${APP_PATH}/src/*.c")

list(APPEND APP_SRCS
    "${APP_PATH}/../src/heartbeat_light.c"
    "${APP_PATH}/../src/pendant_controller.c"
    "$ENV{OPEN_SDK_ROOT}/examples/multimedia/audio_player/tts/src/hello_tuya_16k.c"
    "$ENV{OPEN_SDK_ROOT}/src/ai_components/ai_ui/font/font_puhui_16_4.c"
)

set(APP_INC
    "${APP_PATH}/src"
    "${APP_PATH}/../include"
    "$ENV{OPEN_SDK_ROOT}/examples/multimedia/audio_player/tts/src"
)

add_library(${EXAMPLE_LIB})

target_sources(${EXAMPLE_LIB}
    PRIVATE
        ${APP_SRCS}
)

target_include_directories(${EXAMPLE_LIB}
    PRIVATE
        ${APP_INC}
)

target_compile_options(${EXAMPLE_LIB}
    PRIVATE
        -Wall
        -Wextra
)
