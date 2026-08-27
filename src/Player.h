// Player.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"

class Player {
public:
    // Basic constructor
    Player();

    // Full constructor
    Player(int id, std::string name, std::string color, std::string controller_type)

private:
    int id_{0}
    std::string name_;
    std::string color_;
    std::string controller_type_{"human"};
};
