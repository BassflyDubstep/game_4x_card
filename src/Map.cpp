// Map.cpp
#include "Map.h"

Map::Map() {}

Map::Map(U32 size_x, U32 size_y, Tile::TerrainType default_tile_type)
    : size_x_(size_x), size_y_(size_y), default_tile_type_(default_tile_type) {}
