// Tile.cpp
#include "Tile.h"

Tile::Tile() {}

Tile::Tile(U32 x, U32 y, TerrainType terrain_type, ResourceType resource_type)
    : x_(x), y_(y), terrain_type_(terrain_type), resource_type_(resource_type) {}

std::map<std::string, U32> Tile::get_tile_info() const {
    return {
        {"x: ", x_},
        {"y: ", y_},
        {"terrain_type: ", static_cast<U32>(terrain_type_)},
        {"resource_type: ", static_cast<U32>(resource_type_)}
    };
}