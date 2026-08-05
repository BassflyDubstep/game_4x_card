// Regiment.cpp
#include "Regiment.h"

Regiment::Regiment() {}

Regiment::Regiment(U32 soldier_count, U32 cavalry_count, U32 ranged_count, U32 air_count, U32 navy_count, bool contains_hero,
                   U32 soldier_level, U32 cavalry_level, U32 ranged_level, U32 air_level, U32 navy_level, U32 hero_level,
                   U32 influence)
    : soldier_count_(soldier_count), cavalry_count_(cavalry_count), ranged_count_(ranged_count), air_count_(air_count),
      navy_count_(navy_count), contains_hero_(contains_hero), soldier_level_(soldier_level), cavalry_level_(cavalry_level),
      ranged_level_(ranged_level), air_level_(air_level), navy_level_(navy_level), hero_level_(hero_level),
      influence_(influence) {}