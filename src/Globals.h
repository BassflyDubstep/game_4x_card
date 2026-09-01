// Globals.h
#pragma once

// ---TOP LEVEL GLOBAL VALUES---

// Title of game.
inline constexpr std::string_view GAME_TITLE = "Strategy Card Game";

// Maximum number of cards allowed in a player's hand.
inline constexpr int MAX_HAND_SIZE = 5;



// ---CITY GLOBAL VALUES---

// Default line of sight radius for cities.
inline constexpr int DEFAULT_LINE_OF_SIGHT_RADIUS = 3;

// Additional line of sight radius for capital cities.
inline constexpr int CAPITAL_LINE_OF_SIGHT_BONUS = 1;

// Default attack radius for cities.
inline constexpr int DEFAULT_ATTACK_RADIUS = 1;

// Additional attack radius for capital cities.
inline constexpr int CAPITAL_ATTACK_RADIUS_BONUS = 1;

// Default influence anchors for cities, based on Tile distance.
inline std::unordered_map<int, double> DEFAULT_INFLUENCE_ANCHORS = {{0, 1.0}, {1, 0.8}, {2, 0.4}, {3, 0.1}};

// Influence anchors for capital cities, based on Tile distance.
inline std::unordered_map<int, double> CAPITAL_INFLUENCE_ANCHORS = {{0, 1.0}, {1, 0.9}, {2, 0.5}, {3, 0.2}, {4, 0.1}};

// Number of turns required to stabilize a city after occupation.
inline constexpr int CITY_OCCUPATION_STABILIZATION_TURNS = 5;

// Number of turns required to stabilize a capital city after occupation.
inline constexpr int CAPITAL_OCCUPATION_STABILIZATION_TURNS = 10;

// Minimum influence required to maintain occupation.
inline constexpr double OCCUPATION_INFLUENCE_FLOOR = 0.20;

// Minimum influence required to maintain occupation for capital cities.
inline constexpr double CAPITAL_OCCUPATION_INFLUENCE_FLOOR = 0.10;

// Default amount that an attack is reduced by defense.
inline constexpr double DEFAULT_ATTACK_SCALE = 0.75;

// Default amount that an attack is reduced by defense for capital cities.
inline constexpr double CAPITAL_ATTACK_SCALE = 0.85;

// Number of turns required before a city can fully recover post-capture.
inline constexpr int MIN_POST_CAPTURE_RECOVERY_TURNS = 3;

// The multiplier applied to a city to offset siege.
inline constexpr double SIEGE_RESISTANCE_MULTIPLIER = 6.0;

// Resilience factor applied to a city's defense score.
inline constexpr double DEFENSE_SCALE = 1.0;

// The amount that a siege can reduce a city's resistance.
inline constexpr double BASE_SIEGE_RATE = 0.20;

// The recovery rate of a city's resistance after a siege.
inline constexpr double SIEGE_REGEN_RATE = 0.15;

// Penalty applied to a city's population when it is sacked.
inline constexpr double SACK_POPULATION_PENALTY = 0.30;

// Amount of resistance retained by a city after it is captured.
inline constexpr double POST_CAPTURE_RESISTANCE_RATIO = 0.25;