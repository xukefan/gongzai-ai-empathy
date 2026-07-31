cmake_minimum_required(VERSION 3.16)
project(gongzai_pendant_core C)

set(CMAKE_C_STANDARD 11)
set(CMAKE_C_STANDARD_REQUIRED ON)

add_library(gongzai_pendant_core
    src/heartbeat_light.c
    src/pendant_controller.c
)

target_include_directories(gongzai_pendant_core PUBLIC include)
target_compile_options(gongzai_pendant_core PRIVATE -Wall -Wextra -Werror)

enable_testing()

add_executable(pendant_core_tests tests/test_pendant.c)
target_link_libraries(pendant_core_tests PRIVATE gongzai_pendant_core)
target_compile_options(pendant_core_tests PRIVATE -Wall -Wextra -Werror)

add_test(NAME pendant_core_tests COMMAND pendant_core_tests)
