// Game.cpp
#include "Game.h"
#include "Logger.h"

Game::Game() {
}

Game::Game(std::unique_ptr<Map> map) {
    Logger::info("Game loaded with map.");
    map_ = std::move(map);
}

void Game::run() {
    String input;
    U32 simple_counter = 0;
    while(is_running()) {
        Logger::info("Turn: " + std::to_string(simple_counter));
        Logger::info("The game is running. Continue? (Y/n)");
        std::cin >> input;
        if (input == "Y") {
            simple_counter++;
        } else if (input == "n") {
            running_ = false;
            kill();
        } else {
            Logger::warning("\"" + input + "\"" + " is not a valid choice.");
        }
    }
}

void Game::kill() {
    running_ = false;
}

bool Game::is_running() const {
    return running_;
}
