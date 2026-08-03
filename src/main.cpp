#include "Libraries.h"
#include "Aliases.h"
#include "Game.h"
#include "Map.h"
#include "Logger.h"
#include "Globals.h"

int main() {
    // Initial logging.
    std::cout << "Game Starting: " << GAME_TITLE << std::endl;

    // Initialize game object.
    Game game;

    // Start game.
    game.run();
}
