add_library(game_4x_lib STATIC
    Game.cpp
    Logger.cpp
    Map.cpp
    Player.cpp
)

target_include_directories(game_4x_lib PUBLIC ${CMAKE_CURRENT_SOURCE_DIR})

add_executable(game_4x_card main.cpp)
target_link_libraries(game_4x_card PRIVATE game_4x_lib)
