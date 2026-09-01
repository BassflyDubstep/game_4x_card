// Player.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"
#include "Card.h"
#include "Deck.h"


class Player {
public:
    // Basic constructor
    Player();

    // Full constructor
    Player(int id, std::string name, std::string color, std::string controller_type,
        Deck deck=Deck(), std::vector<Card> hand=std::vector<Card>());

private:
    int id_{0};
    std::string name_;
    std::string color_;
    std::string controller_type_{"human"};
    Deck deck_;
    std::vector<Card> hand_;
};
