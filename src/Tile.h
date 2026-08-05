// Tile.h
#pragma once

#include "Libraries.h"
#include "Aliases.h"
#include "Globals.h"

class Tile {
public:
    enum class TerrainType {
        Grass,
        Water,
        Mountain,
        Forest,
        Desert
    };

    enum class ResourceType {
        None,
        Wood,
        Stone,
        Gold,
        Food
    };

    // Basic constructor.
    Tile();

    // Full constructor.
    Tile(U32 x = 0, U32 y = 0, TerrainType terrain_type = TerrainType::Grass, ResourceType resource_type = ResourceType::None);

    std::map<std::string, U32> get_tile_info() const;

private:
    U32 x_{0};
    U32 y_{0};
    TerrainType terrain_type_{TerrainType::Grass};
    ResourceType resource_type_{ResourceType::None};
};