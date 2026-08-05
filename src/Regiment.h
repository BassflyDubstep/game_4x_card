// Regiment.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"

class Regiment {
public:
    // Basic constructor
    Regiment();

    // Full constructor
    Regiment(U32 soldier_count = 0, U32 cavalry_count = 0, U32 ranged_count = 0, U32 air_count = 0, U32 navy_count = 0, bool contains_hero = false,
             U32 soldier_level = 0, U32 cavalry_level = 0, U32 ranged_level = 0, U32 air_level = 0, U32 navy_level = 0, U32 hero_level = 0,
             U32 influence = 0);

private:
    U32 soldier_count_{0};
    U32 cavalry_count_{0};
    U32 ranged_count_{0};
    U32 air_count_{0};
    U32 navy_count_{0};
    bool contains_hero_{false};

    U32 soldier_level_{0};
    U32 cavalry_level_{0};
    U32 ranged_level_{0};
    U32 air_level_{0};
    U32 navy_level_{0};
    U32 hero_level_{0};

    U32 influence_{0};
};
