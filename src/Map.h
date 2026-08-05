// Map.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"
#include "Tile.h"

class Map {
public:
    // Basic constructor
    Map();

    // Full constructor
    Map(U32 size_x, U32 size_y, Tile::TerrainType default_tile_type = Tile::TerrainType::Grass);

private:
    U32 size_x_{10};
    U32 size_y_{10};
    Tile::TerrainType default_tile_type_{Tile::TerrainType::Grass};
};
