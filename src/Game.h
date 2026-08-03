#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"
#include "Map.h"
#include "Player.h"

class Game {
public:
    // Basic constructor.
    Game();

    // Constructor loads a map.
    Game(std::unique_ptr<Map> map);

    // Run the game loop.
    void run();

    // Kill the game loop.
    void kill();

    // Determine if the game is running.
    bool is_running() const;

private:
    std::unique_ptr<Map> map_;
    bool running_ = 1;
};
