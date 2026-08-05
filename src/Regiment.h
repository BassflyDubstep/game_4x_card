// Regiment.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"

class Regiment {
public:
    // Basic constructor.
    Regiment();

    // Full constructor.
    

private:
    U32 soldier_count_;
    U32 cavalry_count_;
    U32 ranged_count_;
    U32 air_count_;
    U32 navy_count_;
    bool contains_hero_;

    U32 soldier_level_;
    U32 cavalry_level_;
    U32 ranged_level_;
    U32 air_level_;
    U32 navy_level_;
    U32 hero_level_;

    double influence_;
};
