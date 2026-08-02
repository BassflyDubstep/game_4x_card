cmake_minimum_required(VERSION 3.16)
project(game_4x_card VERSION 0.1 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Source tree
add_subdirectory(src)

# Tests
enable_testing()
add_subdirectory(tests)
