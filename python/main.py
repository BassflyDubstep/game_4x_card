# main.py
import os
import sys
import math
import random
from pathlib import Path
from colorama import Fore, Style, init as colorama_init

colorama_init(autoreset=True)

class Player:

    def __init__(self, id: int, name: str, color: str):
        self.id = id
        self.name = name
        self.color = color

class City:

    _city_symbols = {'City': 'C', 'Capital': '*C'}
    DEFAULT_LINE_OF_SIGHT_RADIUS = 3
    CAPITAL_LINE_OF_SIGHT_BONUS = 1
    DEFAULT_INFLUENCE_ANCHORS = {0: 1.0, 1: 0.8, 2: 0.4, 3: 0.1}
    CAPITAL_INFLUENCE_ANCHORS = {0: 1.0, 1: 0.9, 2: 0.5, 3: 0.2, 4: 0.1}
    RESISTANCE_MULTIPLIER = 5.0
    DEFENSE_SCALE = 1.0
    BASE_SIEGE_RATE = 0.20
    SIEGE_REGEN_RATE = 0.15
    SACK_POPULATION_PENALTY = 0.30
    
    def __init__(self, id: int, name: str, owner_id: int,
                 population: int = 1000, is_capital: bool = False,
                 defense_score: float = None, line_of_sight_radius: int = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.population = population
        self.is_capital = is_capital
        self.defense_score = defense_score if defense_score is not None else self._default_defense_score()
        self.line_of_sight_radius = self._validate_line_of_sight_radius(
            self.DEFAULT_LINE_OF_SIGHT_RADIUS if line_of_sight_radius is None else line_of_sight_radius
        )
        self.influence_radius_bonus = 0
        self.influence_score_bonus = 0.0
        self.influence_score_multiplier = 1.0
        self.influence_profile_anchors = self._default_influence_anchors()
        self.max_siege_resistance = self._default_max_siege_resistance()
        self.siege_resistance = self.max_siege_resistance
        self._update_symbol()

    def mark_as_capital(self):
        self.is_capital = True
        self.defense_score = self._default_defense_score()
        self.influence_profile_anchors = self._default_influence_anchors()
        self.max_siege_resistance = self._default_max_siege_resistance()
        self.siege_resistance = self.max_siege_resistance
        self._update_symbol()

    def _default_defense_score(self):
        # Population and capital status provide a simple defensive baseline.
        return round(20 + (self.population / 200) + (10 if self.is_capital else 0), 2)

    def _default_max_siege_resistance(self):
        return round(self.defense_score * self.RESISTANCE_MULTIPLIER, 2)

    def _validate_line_of_sight_radius(self, radius: int):
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('City line of sight radius must be a non-negative integer')
        return radius

    def _default_influence_anchors(self):
        return dict(
            self.CAPITAL_INFLUENCE_ANCHORS if self.is_capital else self.DEFAULT_INFLUENCE_ANCHORS
        )

    def effective_line_of_sight_radius(self):
        return max(
            0,
            self.line_of_sight_radius +
            self.influence_radius_bonus +
            (self.CAPITAL_LINE_OF_SIGHT_BONUS if self.is_capital else 0),
        )

    def get_influence_profile(self):
        return self._build_influence_profile(
            self.effective_line_of_sight_radius(),
            self.influence_profile_anchors,
        )

    def get_influence_at_distance(self, distance: int):
        if not isinstance(distance, int) or distance < 0:
            raise ValueError('Influence distance must be a non-negative integer')

        influence_profile = self.get_influence_profile()
        base_score = influence_profile.get(distance, 0.0)
        modified_score = (base_score + self.influence_score_bonus) * self.influence_score_multiplier
        return max(0.0, min(1.0, round(modified_score, 4)))

    @staticmethod
    def _build_influence_profile(max_radius: int, anchors: dict[int, float]):
        if max_radius < 0:
            return {}

        normalized_anchors = {
            distance: max(0.0, min(1.0, float(score)))
            for distance, score in anchors.items()
            if isinstance(distance, int) and distance >= 0
        }
        if 0 not in normalized_anchors:
            normalized_anchors[0] = 1.0

        anchor_distances = sorted(normalized_anchors)
        last_anchor_distance = anchor_distances[-1]
        last_anchor_value = normalized_anchors[last_anchor_distance]
        profile = {}

        for distance in range(max_radius + 1):
            if distance in normalized_anchors:
                profile[distance] = round(normalized_anchors[distance], 4)
                continue

            lower_distance = max(d for d in anchor_distances if d < distance)
            upper_candidates = [d for d in anchor_distances if d > distance]
            if upper_candidates:
                upper_distance = min(upper_candidates)
                lower_position = math.log(lower_distance + 1)
                upper_position = math.log(upper_distance + 1)
                current_position = math.log(distance + 1)
                if math.isclose(lower_position, upper_position):
                    interpolated = normalized_anchors[lower_distance]
                else:
                    interpolation_ratio = (
                        (current_position - lower_position) /
                        (upper_position - lower_position)
                    )
                    interpolated = normalized_anchors[lower_distance] + (
                        (normalized_anchors[upper_distance] - normalized_anchors[lower_distance]) *
                        interpolation_ratio
                    )
            else:
                tail_distance = distance - last_anchor_distance
                interpolated = last_anchor_value / (1 + math.log(tail_distance + 1, 2))

            profile[distance] = round(max(0.0, min(1.0, interpolated)), 4)
        return profile

    def _update_symbol(self):
        self.symbol = f'{"*C" if self.is_capital else "C"}{self.id}({self.owner_id})'

class Tile:

    _allowable_types = {
        'grass':    {'passable_foot': True,  'passable_water': False, 'symbol': '.'},
        'water':    {'passable_foot': False, 'passable_water': True,  'symbol': '~'},
        'mountain': {'passable_foot': False, 'passable_water': False, 'symbol': '^'},
        'forest':   {'passable_foot': True,  'passable_water': False, 'symbol': '%'},
        'hill':     {'passable_foot': True,  'passable_water': False, 'symbol': 'n'},
    }

    def __init__(self, type: str = 'grass', x: int = None, y: int = None,
                 regiment_id: int = None, city_id: int = None,
                 resource_id: int = None):
        if type not in Tile._allowable_types.keys():
            raise ValueError(f'Invalid tile type: {type}')
        self.type = type
        self.x = x
        self.y = y
        self.regiment_id = regiment_id
        self.city_id = city_id
        self.resource_id = resource_id
        self.passable_foot = self._allowable_types[type]['passable_foot']
        self.passable_water = self._allowable_types[type]['passable_water']
        self.symbol = self._allowable_types[type]['symbol']
        self.influence_scores: dict[int, float] = {}
        self.influence_owner_id: int | None = None
        self.is_influence_contested = False

class Card:

    def __init__(self):
        pass

class Regiment:

    REGIMENT_ATTACK_WEIGHTS = {
        'infantry': 1.0,
        'ranged': 0.85,
        'cavalry': 1.15,
    }
    BASE_BATTLE_RATE = 0.25
    FORCE_SIZE_EXPONENT = 0.5
    RANGED_ATTACK_RADIUS = 2
    DEFAULT_LINE_OF_SIGHT_RADIUS = 1
    TILE_INFLUENCE_SCORE = 1.0
    CITY_INFLUENCE_SUPPORT_BONUS = 0.25
    CITY_INFLUENCE_DISRUPTION_PENALTY = 0.25
    HERO_INFLUENCE_BONUS = 0.25
    HERO_INFLUENCE_RADIUS = 1

    CITY_ATTACK_WEIGHTS = {
        'infantry': 0.8,
        'ranged': 0.7,
        'cavalry': 0.6,
        'siege': 1.6,
    }

    def __init__(self, id: int = None, name: str = 'Unnamed Regiment', owner_id: int = None,
                 infantry: int = 0, ranged: int = 0, cavalry: int = 0,
                 siege: int = 0, heroes: list[str] = None,
                 line_of_sight_radius: int = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.infantry = self._validate_unit_count(infantry, 'infantry')
        self.ranged = self._validate_unit_count(ranged, 'ranged')
        self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        self.siege = self._validate_unit_count(siege, 'siege')
        self.heroes = list(heroes) if heroes is not None else []
        self.line_of_sight_radius = self._validate_line_of_sight_radius(
            self.DEFAULT_LINE_OF_SIGHT_RADIUS if line_of_sight_radius is None else line_of_sight_radius
        )
        self.influence_radius_bonus = 0
        self.tile_influence_score = self.TILE_INFLUENCE_SCORE
        self.city_influence_support_bonus = self.CITY_INFLUENCE_SUPPORT_BONUS
        self.city_influence_disruption_penalty = self.CITY_INFLUENCE_DISRUPTION_PENALTY
        self.hero_influence_bonus = self.HERO_INFLUENCE_BONUS
        self.hero_influence_radius = self.HERO_INFLUENCE_RADIUS
        self.influence_score_multiplier = 1.0

        self.regiment_attack_score = 0.0
        self.city_attack_score = 0.0
        self.movement_spent_this_turn = 0
        self.reorganized_this_turn = False
        self.recalculate_attack_scores()

    def _validate_unit_count(self, value: int, unit_type: str):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f'{unit_type} count must be a non-negative integer')
        return value

    def _validate_line_of_sight_radius(self, radius: int):
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('Regiment line of sight radius must be a non-negative integer')
        return radius

    def total_units(self):
        return self.infantry + self.ranged + self.cavalry + self.siege

    def hero_count(self):
        return len(self.heroes)

    def effective_line_of_sight_radius(self):
        return max(0, self.line_of_sight_radius + self.influence_radius_bonus)

    def has_hero_influence(self):
        return self.hero_count() > 0 and self.hero_influence_bonus > 0

    def update_composition(self, infantry: int = None, ranged: int = None,
                           cavalry: int = None, siege: int = None):
        if infantry is not None:
            self.infantry = self._validate_unit_count(infantry, 'infantry')
        if ranged is not None:
            self.ranged = self._validate_unit_count(ranged, 'ranged')
        if cavalry is not None:
            self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        if siege is not None:
            self.siege = self._validate_unit_count(siege, 'siege')
        self.recalculate_attack_scores()

    def add_hero(self, hero_name: str):
        normalized_name = str(hero_name).strip()
        if not normalized_name:
            raise ValueError('Hero name must be a non-empty string')
        self.heroes.append(normalized_name)
        self.recalculate_attack_scores()

    def symbol(self):
        return f'R{self.id}({self.owner_id})'

    def movement_range(self):
        # Larger and stronger regiments move less distance per turn.
        movement = 8 - (self.total_units() / 25) - (self.regiment_attack_score / 120)
        return max(1, int(round(movement)))

    def movement_remaining(self):
        return max(0, self.movement_range() - self.movement_spent_this_turn)

    def can_move_distance(self, distance: int):
        return distance <= self.movement_remaining()

    def record_movement(self, distance: int):
        self.movement_spent_this_turn += max(0, distance)

    def consume_movement(self):
        self.movement_spent_this_turn = self.movement_range()

    def reset_turn_movement(self):
        self.movement_spent_this_turn = 0
        self.reorganized_this_turn = False

    def mark_reorganized_this_turn(self):
        self.reorganized_this_turn = True
        self.consume_movement()

    def has_ranged_attack_capability(self):
        return self.ranged > 0 or getattr(self, 'navy', 0) > 0

    def attack_range(self):
        return self.RANGED_ATTACK_RADIUS if self.has_ranged_attack_capability() else 1

    def can_attack_distance(self, distance: int):
        return 0 <= distance <= self.attack_range()

    def recalculate_attack_scores(self):
        self.regiment_attack_score = self._compute_weighted_score(
            self.REGIMENT_ATTACK_WEIGHTS,
            include_siege=False,
        )
        self.city_attack_score = self._compute_weighted_score(
            self.CITY_ATTACK_WEIGHTS,
            include_siege=True,
        )

    def _compute_weighted_score(self, weights: dict[str, float], include_siege: bool):
        unit_counts = {
            'infantry': self.infantry,
            'ranged': self.ranged,
            'cavalry': self.cavalry,
        }
        if include_siege:
            unit_counts['siege'] = self.siege

        total_weighted_units = 0.0
        total_units = 0
        for unit_type, count in unit_counts.items():
            total_weighted_units += count * weights[unit_type]
            total_units += count

        if total_units == 0:
            return 0.0

        hero_bonus = 1 + (0.05 * self.hero_count())
        return round((total_weighted_units / total_units) * hero_bonus * 100, 2)

class Map:

    MAX_INFLUENCE_SCORE = 1.0
    PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT = 100.0
    INFLUENCE_EPSILON = 0.0001
    MIN_VISIBLE_INFLUENCE_SCORE = 0.01
    MIN_VISIBLE_INFLUENCE_COLOR_BLEND = 0.4

    def __init__(self, width: int = 10, height: int = 10,
                 default_tile: str = 'grass'):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.tiles = {}
        self.players: dict[int, Player] = {}
        self.cities: dict[int, City] = {}
        self.regiments: dict[int, Regiment] = {}
        self.player_discovered_tiles: dict[int, set[tuple[int, int]]] = {}
        self.next_regiment_id = 1
        self.resolved_regiment_battles_this_turn: set[tuple[int, int]] = set()
        self.resolved_sieges_this_turn: set[int] = set()

    def add_player(self, player: Player):
        self.players[player.id] = player
        self._ensure_player_discovery_entry(player.id)
        self.recalculate_tile_influence()

    def add_city(self, city: City):
        if city.owner_id not in self.players:
            raise ValueError(f'City {city.id} references missing player {city.owner_id}')
        self.cities[city.id] = city
        self.recalculate_tile_influence()
        if self.get_city_location(city.id) is not None:
            self.update_player_discovery(city.owner_id)

    def get_player(self, player_id: int):
        return self.players.get(player_id)

    def get_player_total_influence_score(self, player_id: int):
        if player_id not in self.players:
            raise ValueError(f'Player {player_id} does not exist')

        total_score = 0.0
        for tile in self.tiles.values():
            total_score += (
                tile.influence_scores.get(player_id, 0.0) *
                self.PLAYER_TOTAL_INFLUENCE_TILE_WEIGHT
            )
        return round(total_score, 2)

    def get_player_influence_rankings(self):
        rankings = []
        for player in self.players.values():
            rankings.append((player, self.get_player_total_influence_score(player.id)))
        return sorted(rankings, key=lambda entry: (-entry[1], entry[0].id))

    def get_city(self, city_id: int):
        return self.cities.get(city_id)

    def get_city_owner(self, city_id: int):
        city = self.get_city(city_id)
        if city is None:
            return None
        return self.get_player(city.owner_id)

    def get_city_location(self, city_id: int):
        for (x, y), tile in self.tiles.items():
            if tile.city_id == city_id:
                return (x, y)
        return None

    def get_regiment(self, regiment_id: int):
        return self.regiments.get(regiment_id)

    def get_regiment_location(self, regiment_id: int):
        for (x, y), tile in self.tiles.items():
            if tile.regiment_id == regiment_id:
                return (x, y)
        return None

    def get_regiment_at(self, x: int, y: int):
        tile = self.tiles.get((x, y))
        if tile is None or tile.regiment_id is None:
            return None
        return self.get_regiment(tile.regiment_id)

    def get_tile_distance(self, origin: tuple[int, int], target: tuple[int, int]):
        if origin is None or target is None:
            raise ValueError('Both origin and target locations are required')
        return max(abs(target[0] - origin[0]), abs(target[1] - origin[1]))

    def _ensure_player_discovery_entry(self, player_id: int):
        if player_id not in self.player_discovered_tiles:
            self.player_discovered_tiles[player_id] = set()
        return self.player_discovered_tiles[player_id]

    def get_tiles_in_radius(self, origin: tuple[int, int], radius: int):
        if origin is None:
            return set()
        if not isinstance(radius, int) or radius < 0:
            raise ValueError('Line of sight radius must be a non-negative integer')

        tiles_in_radius = set()
        origin_x, origin_y = origin
        min_x = max(0, origin_x - radius)
        max_x = min(self.width - 1, origin_x + radius)
        min_y = max(0, origin_y - radius)
        max_y = min(self.height - 1, origin_y + radius)
        for x in range(min_x, max_x + 1):
            for y in range(min_y, max_y + 1):
                tiles_in_radius.add((x, y))
        return tiles_in_radius

    def _clamp_influence_score(self, score: float):
        return round(max(0.0, min(self.MAX_INFLUENCE_SCORE, float(score))), 4)

    def _set_tile_influence(self, tile: Tile, influence_scores: dict[int, float]):
        normalized_scores = {
            player_id: self._clamp_influence_score(influence_scores.get(player_id, 0.0))
            for player_id in self.players
        }
        tile.influence_scores = normalized_scores

        if not normalized_scores:
            tile.influence_owner_id = None
            tile.is_influence_contested = False
            return

        highest_score = max(normalized_scores.values(), default=0.0)
        if highest_score <= self.INFLUENCE_EPSILON:
            tile.influence_owner_id = None
            tile.is_influence_contested = False
            return

        winning_players = [
            player_id for player_id, score in normalized_scores.items()
            if abs(score - highest_score) <= self.INFLUENCE_EPSILON
        ]
        tile.influence_owner_id = winning_players[0] if len(winning_players) == 1 else None
        tile.is_influence_contested = len(winning_players) > 1

    def recalculate_tile_influence(self):
        if not self.tiles:
            return

        city_influence_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_support_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_disruption_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        hero_influence_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }
        regiment_tile_control_by_tile = {
            position: {player_id: 0.0 for player_id in self.players}
            for position in self.tiles
        }

        for city in self.cities.values():
            city_location = self.get_city_location(city.id)
            if city_location is None or city.owner_id not in self.players:
                continue

            for position in self.get_tiles_in_radius(city_location, city.effective_line_of_sight_radius()):
                distance = self.get_tile_distance(city_location, position)
                influence_score = city.get_influence_at_distance(distance)
                if influence_score <= self.INFLUENCE_EPSILON:
                    continue
                city_influence_by_tile[position][city.owner_id] = self._clamp_influence_score(
                    city_influence_by_tile[position][city.owner_id] + influence_score
                )

        for regiment in self.regiments.values():
            regiment_location = self.get_regiment_location(regiment.id)
            if regiment_location is None or regiment.owner_id not in self.players:
                continue

            for position in self.get_tiles_in_radius(regiment_location, regiment.effective_line_of_sight_radius()):
                if city_influence_by_tile[position].get(regiment.owner_id, 0.0) > self.INFLUENCE_EPSILON:
                    regiment_support_by_tile[position][regiment.owner_id] = self._clamp_influence_score(
                        regiment_support_by_tile[position][regiment.owner_id] +
                        (regiment.city_influence_support_bonus * regiment.influence_score_multiplier)
                    )

                for player_id in self.players:
                    if player_id == regiment.owner_id:
                        continue
                    if city_influence_by_tile[position].get(player_id, 0.0) <= self.INFLUENCE_EPSILON:
                        continue
                    regiment_disruption_by_tile[position][player_id] = self._clamp_influence_score(
                        regiment_disruption_by_tile[position][player_id] +
                        (regiment.city_influence_disruption_penalty * regiment.influence_score_multiplier)
                    )

            if regiment.has_hero_influence():
                for position in self.get_tiles_in_radius(regiment_location, regiment.hero_influence_radius):
                    hero_influence_by_tile[position][regiment.owner_id] = self._clamp_influence_score(
                        hero_influence_by_tile[position][regiment.owner_id] +
                        (regiment.hero_influence_bonus * regiment.influence_score_multiplier)
                    )

            regiment_tile_control_by_tile[regiment_location][regiment.owner_id] = self._clamp_influence_score(
                regiment_tile_control_by_tile[regiment_location][regiment.owner_id] +
                (regiment.tile_influence_score * regiment.influence_score_multiplier)
            )

        for position, tile in self.tiles.items():
            total_influence = {}
            for player_id in self.players:
                influence_score = (
                    city_influence_by_tile[position][player_id] +
                    regiment_support_by_tile[position][player_id] +
                    hero_influence_by_tile[position][player_id] -
                    regiment_disruption_by_tile[position][player_id]
                )
                influence_score = self._clamp_influence_score(influence_score)
                influence_score = max(
                    influence_score,
                    regiment_tile_control_by_tile[position][player_id],
                )
                total_influence[player_id] = self._clamp_influence_score(influence_score)
            self._set_tile_influence(tile, total_influence)

    def get_player_visible_tiles(self, player_id: int):
        if player_id not in self.players:
            return set()

        visible_tiles = set()
        for city in self.cities.values():
            if city.owner_id != player_id:
                continue
            visible_tiles.update(self.get_tiles_in_radius(
                self.get_city_location(city.id),
                city.effective_line_of_sight_radius(),
            ))

        for regiment in self.regiments.values():
            if regiment.owner_id != player_id:
                continue
            visible_tiles.update(self.get_tiles_in_radius(
                self.get_regiment_location(regiment.id),
                regiment.effective_line_of_sight_radius(),
            ))
        return visible_tiles

    def get_player_discovered_tiles(self, player_id: int):
        return self._ensure_player_discovery_entry(player_id)

    def update_player_discovery(self, player_id: int):
        discovered_tiles = self._ensure_player_discovery_entry(player_id)
        discovered_tiles.update(self.get_player_visible_tiles(player_id))
        return discovered_tiles

    def refresh_all_player_discovery(self):
        self.recalculate_tile_influence()
        for player_id in self.players:
            self.update_player_discovery(player_id)

    def is_tile_visible_to_player(self, x: int, y: int, player_id: int):
        return (x, y) in self.get_player_visible_tiles(player_id)

    def is_city_visible_to_player(self, city_id: int, player_id: int):
        location = self.get_city_location(city_id)
        return location is not None and self.is_tile_visible_to_player(location[0], location[1], player_id)

    def is_regiment_visible_to_player(self, regiment_id: int, player_id: int):
        location = self.get_regiment_location(regiment_id)
        return location is not None and self.is_tile_visible_to_player(location[0], location[1], player_id)

    def add_regiment(self, regiment: Regiment, x: int, y: int):
        if regiment.owner_id not in self.players:
            raise ValueError(f'Regiment owner {regiment.owner_id} does not exist')
        if (x, y) not in self.tiles:
            raise ValueError(f'Tile ({x}, {y}) is out of bounds')
        tile = self.tiles[(x, y)]
        if tile.regiment_id is not None:
            raise ValueError(f'Tile ({x}, {y}) already has a regiment')
        if not tile.passable_foot:
            raise ValueError(f'Tile ({x}, {y}) is not passable for land regiments')

        if regiment.id is None:
            regiment.id = self.next_regiment_id
            self.next_regiment_id += 1
        elif regiment.id in self.regiments:
            raise ValueError(f'Regiment id {regiment.id} already exists')
        else:
            self.next_regiment_id = max(self.next_regiment_id, regiment.id + 1)

        self.regiments[regiment.id] = regiment
        tile.regiment_id = regiment.id
        self.recalculate_tile_influence()
        self.update_player_discovery(regiment.owner_id)

    def move_regiment(self, regiment_id: int, target_x: int, target_y: int):
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')

        start = self.get_regiment_location(regiment_id)
        if start is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')
        if (target_x, target_y) not in self.tiles:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is out of bounds')

        target_tile = self.tiles[(target_x, target_y)]
        if target_tile.regiment_id is not None:
            raise ValueError(f'Target tile ({target_x}, {target_y}) already has a regiment')
        if not target_tile.passable_foot:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments')

        delta_x = abs(target_x - start[0])
        delta_y = abs(target_y - start[1])
        distance = max(delta_x, delta_y)
        if not regiment.can_move_distance(distance):
            raise ValueError(
                f'Regiment {regiment_id} has {regiment.movement_remaining()} movement remaining this turn '
                f'and cannot move {distance} tiles'
            )

        self.tiles[start].regiment_id = None
        target_tile.regiment_id = regiment_id
        regiment.record_movement(distance)
        self.recalculate_tile_influence()
        self.update_player_discovery(regiment.owner_id)

    def split_regiment(self, regiment_id: int, target_x: int, target_y: int,
                       split_counts: dict[str, int], new_name: str = None):
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')
        if regiment.total_units() == 0:
            raise ValueError(f'Regiment {regiment_id} has no units remaining')
        if regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {regiment_id} has already split or combined this turn')
        if regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {regiment_id} has no movement remaining to perform a split')

        start = self.get_regiment_location(regiment_id)
        if start is None:
            raise ValueError(f'Regiment {regiment_id} is not on the map')
        if (target_x, target_y) not in self.tiles:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is out of bounds')
        if self.get_tile_distance(start, (target_x, target_y)) != 1:
            raise ValueError('Split regiment must form on an adjacent tile')

        target_tile = self.tiles[(target_x, target_y)]
        if target_tile.regiment_id is not None:
            raise ValueError(f'Target tile ({target_x}, {target_y}) already has a regiment')
        if not target_tile.passable_foot:
            raise ValueError(f'Target tile ({target_x}, {target_y}) is not passable for land regiments')

        unit_types = ('infantry', 'ranged', 'cavalry', 'siege')
        transfer_counts = {}
        for unit_type in unit_types:
            transfer_count = split_counts.get(unit_type, 0)
            if not isinstance(transfer_count, int) or transfer_count < 0:
                raise ValueError(f'Split count for {unit_type} must be a non-negative integer')
            if transfer_count > getattr(regiment, unit_type):
                raise ValueError(f'Regiment {regiment_id} does not have enough {unit_type} to split that amount')
            transfer_counts[unit_type] = transfer_count

        transferred_total = sum(transfer_counts.values())
        if transferred_total == 0:
            raise ValueError('Split must transfer at least one unit into the new regiment')

        remaining_counts = {
            unit_type: getattr(regiment, unit_type) - transfer_counts[unit_type]
            for unit_type in unit_types
        }
        if sum(remaining_counts.values()) == 0:
            raise ValueError('Split must leave at least one unit in the original regiment')

        regiment_name = str(new_name).strip() if new_name is not None else ''
        if not regiment_name:
            regiment_name = f'{regiment.name} Detachment'

        split_regiment = Regiment(
            name=regiment_name,
            owner_id=regiment.owner_id,
            infantry=transfer_counts['infantry'],
            ranged=transfer_counts['ranged'],
            cavalry=transfer_counts['cavalry'],
            siege=transfer_counts['siege'],
        )
        self.add_regiment(split_regiment, target_x, target_y)
        regiment.update_composition(
            infantry=remaining_counts['infantry'],
            ranged=remaining_counts['ranged'],
            cavalry=remaining_counts['cavalry'],
            siege=remaining_counts['siege'],
        )
        regiment.mark_reorganized_this_turn()
        split_regiment.mark_reorganized_this_turn()
        self.recalculate_tile_influence()
        return split_regiment

    def combine_regiments(self, source_regiment_id: int, target_regiment_id: int):
        if source_regiment_id == target_regiment_id:
            raise ValueError('A regiment cannot combine into itself')

        source_regiment = self.get_regiment(source_regiment_id)
        if source_regiment is None:
            raise ValueError(f'Regiment {source_regiment_id} does not exist')
        target_regiment = self.get_regiment(target_regiment_id)
        if target_regiment is None:
            raise ValueError(f'Regiment {target_regiment_id} does not exist')
        if source_regiment.owner_id != target_regiment.owner_id:
            raise ValueError('Only regiments from the same empire may combine')
        if source_regiment.total_units() == 0:
            raise ValueError(f'Regiment {source_regiment_id} has no units remaining')
        if target_regiment.total_units() == 0:
            raise ValueError(f'Regiment {target_regiment_id} has no units remaining')
        if source_regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {source_regiment_id} has already split or combined this turn')
        if target_regiment.reorganized_this_turn:
            raise ValueError(f'Regiment {target_regiment_id} has already split or combined this turn')
        if source_regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {source_regiment_id} has no movement remaining to perform a combine')
        if target_regiment.movement_remaining() < 1:
            raise ValueError(f'Regiment {target_regiment_id} has no movement remaining to perform a combine')

        source_location = self.get_regiment_location(source_regiment_id)
        target_location = self.get_regiment_location(target_regiment_id)
        if source_location is None:
            raise ValueError(f'Regiment {source_regiment_id} is not on the map')
        if target_location is None:
            raise ValueError(f'Regiment {target_regiment_id} is not on the map')
        if self.get_tile_distance(source_location, target_location) != 1:
            raise ValueError('Regiments must be on adjacent tiles to combine')

        target_regiment.update_composition(
            infantry=target_regiment.infantry + source_regiment.infantry,
            ranged=target_regiment.ranged + source_regiment.ranged,
            cavalry=target_regiment.cavalry + source_regiment.cavalry,
            siege=target_regiment.siege + source_regiment.siege,
        )
        target_regiment.heroes.extend(source_regiment.heroes)
        target_regiment.recalculate_attack_scores()
        self._remove_regiment_from_map(source_regiment_id)
        target_regiment.mark_reorganized_this_turn()
        self.recalculate_tile_influence()
        return target_regiment

    def resolve_regiment_battle(self, regiment_a_id: int, regiment_b_id: int) -> dict:
        regiment_a = self.get_regiment(regiment_a_id)
        if regiment_a is None:
            raise ValueError(f'Regiment {regiment_a_id} does not exist')
        regiment_b = self.get_regiment(regiment_b_id)
        if regiment_b is None:
            raise ValueError(f'Regiment {regiment_b_id} does not exist')
        if self.get_regiment_location(regiment_a_id) is None:
            raise ValueError(f'Regiment {regiment_a_id} is not on the map')
        if self.get_regiment_location(regiment_b_id) is None:
            raise ValueError(f'Regiment {regiment_b_id} is not on the map')
        if regiment_a.total_units() == 0:
            raise ValueError(f'Regiment {regiment_a_id} has no units remaining')
        if regiment_b.total_units() == 0:
            raise ValueError(f'Regiment {regiment_b_id} has no units remaining')
        if regiment_a.owner_id == regiment_b.owner_id:
            raise ValueError(f'Regiments {regiment_a_id} and {regiment_b_id} belong to the same owner')

        battle_key = tuple(sorted((regiment_a_id, regiment_b_id)))
        if battle_key in self.resolved_regiment_battles_this_turn:
            raise ValueError(
                f'Battle between Regiment {regiment_a_id} and Regiment {regiment_b_id} has already been resolved this turn'
            )

        power_a = regiment_a.regiment_attack_score * (regiment_a.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        power_b = regiment_b.regiment_attack_score * (regiment_b.total_units() ** Regiment.FORCE_SIZE_EXPONENT)
        total_power = power_a + power_b
        if total_power == 0:
            loss_fraction_a = 0.0
            loss_fraction_b = 0.0
        else:
            loss_fraction_a = Regiment.BASE_BATTLE_RATE * (power_b / total_power)
            loss_fraction_b = Regiment.BASE_BATTLE_RATE * (power_a / total_power)

        casualties_a = self._apply_regiment_battle_losses(
            regiment_a,
            min(
                regiment_a.infantry + regiment_a.ranged + regiment_a.cavalry,
                int(math.floor((regiment_a.total_units() * loss_fraction_a) + 0.5)),
            ),
        )
        casualties_b = self._apply_regiment_battle_losses(
            regiment_b,
            min(
                regiment_b.infantry + regiment_b.ranged + regiment_b.cavalry,
                int(math.floor((regiment_b.total_units() * loss_fraction_b) + 0.5)),
            ),
        )

        remaining_units_a = regiment_a.total_units()
        remaining_units_b = regiment_b.total_units()
        defeated_a = remaining_units_a == 0
        defeated_b = remaining_units_b == 0

        if defeated_a:
            self._remove_regiment_from_map(regiment_a_id)
        if defeated_b:
            self._remove_regiment_from_map(regiment_b_id)

        self.resolved_regiment_battles_this_turn.add(battle_key)
        return {
            'regiment_a_id': regiment_a_id,
            'regiment_b_id': regiment_b_id,
            'casualties_a': casualties_a,
            'casualties_b': casualties_b,
            'remaining_units_a': remaining_units_a,
            'remaining_units_b': remaining_units_b,
            'defeated_a': defeated_a,
            'defeated_b': defeated_b,
        }

    def attack_regiment(self, attacker_id: int, defender_id: int) -> dict:
        if attacker_id == defender_id:
            raise ValueError('A regiment cannot attack itself')

        attacker = self.get_regiment(attacker_id)
        if attacker is None:
            raise ValueError(f'Regiment {attacker_id} does not exist')
        defender = self.get_regiment(defender_id)
        if defender is None:
            raise ValueError(f'Regiment {defender_id} does not exist')

        attacker_location = self.get_regiment_location(attacker_id)
        defender_location = self.get_regiment_location(defender_id)
        if attacker_location is None:
            raise ValueError(f'Regiment {attacker_id} is not on the map')
        if defender_location is None:
            raise ValueError(f'Regiment {defender_id} is not on the map')

        attack_distance = self.get_tile_distance(attacker_location, defender_location)
        if not attacker.can_attack_distance(attack_distance):
            raise ValueError(
                f'Regiment {attacker_id} may attack up to {attacker.attack_range()} tile(s), '
                f'but Regiment {defender_id} is {attack_distance} tile(s) away'
            )

        result = self.resolve_regiment_battle(attacker_id, defender_id)
        result['attack_distance'] = attack_distance
        return result

    def resolve_siege(self, regiment_id: int = None, city_id: int = None) -> dict:
        if city_id is None:
            raise ValueError('City id is required')

        city = self.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist')
        city_location = self.get_city_location(city_id)
        if city_location is None:
            raise ValueError(f'City {city_id} is not on the map')
        if city_id in self.resolved_sieges_this_turn:
            raise ValueError(f'Siege resolution for City {city_id} has already been resolved this turn')

        regiment = None
        if regiment_id is not None:
            regiment = self.get_regiment(regiment_id)
            if regiment is None:
                raise ValueError(f'Regiment {regiment_id} does not exist')
            if regiment.total_units() == 0:
                raise ValueError(f'Regiment {regiment_id} has no units remaining')

        resistance_before = city.siege_resistance
        sacked = False
        previous_owner_id = city.owner_id
        regiment_location = self.get_regiment_location(regiment_id) if regiment_id is not None else None
        attack_distance = self.get_tile_distance(regiment_location, city_location) if regiment_location is not None else None
        if (
            regiment is not None and
            regiment_location is not None and
            regiment.owner_id != city.owner_id and
            not regiment.can_attack_distance(attack_distance)
        ):
            raise ValueError(
                f'Regiment {regiment_id} may attack up to {regiment.attack_range()} tile(s), '
                f'but City {city_id} is {attack_distance} tile(s) away'
            )
        is_besieging = (
            regiment is not None and
            regiment_location is not None and
            regiment.can_attack_distance(attack_distance) and
            regiment.owner_id != city.owner_id
        )

        if is_besieging:
            siege_pressure = regiment.city_attack_score * regiment.total_units()
            total_pressure = siege_pressure + (city.defense_score * City.DEFENSE_SCALE)
            loss_fraction = 0.0 if total_pressure == 0 else City.BASE_SIEGE_RATE * (siege_pressure / total_pressure)
            resistance_loss = city.siege_resistance * loss_fraction
            city.siege_resistance = round(max(0.0, city.siege_resistance - resistance_loss), 2)

            if city.siege_resistance <= 0:
                city.owner_id = regiment.owner_id
                city.population = round(city.population * (1 - City.SACK_POPULATION_PENALTY))
                city.siege_resistance = city.max_siege_resistance
                city._update_symbol()
                self.recalculate_tile_influence()
                self.update_player_discovery(city.owner_id)
                sacked = True
        else:
            city.siege_resistance = round(
                min(
                    city.max_siege_resistance,
                    city.siege_resistance + (City.SIEGE_REGEN_RATE * city.max_siege_resistance),
                ),
                2,
            )

        self.resolved_sieges_this_turn.add(city_id)
        result = {
            'city_id': city_id,
            'regiment_id': regiment_id,
            'resistance_before': resistance_before,
            'resistance_after': city.siege_resistance,
            'max_resistance': city.max_siege_resistance,
            'sacked': sacked,
        }
        if sacked:
            result['previous_owner_id'] = previous_owner_id
            result['new_owner_id'] = city.owner_id
        return result

    def attack_city(self, regiment_id: int, city_id: int) -> dict:
        regiment = self.get_regiment(regiment_id)
        if regiment is None:
            raise ValueError(f'Regiment {regiment_id} does not exist')

        city = self.get_city(city_id)
        if city is None:
            raise ValueError(f'City {city_id} does not exist')
        if regiment.owner_id == city.owner_id:
            raise ValueError(f'Regiment {regiment_id} and City {city_id} belong to the same owner')

        attack_result = self.resolve_siege(regiment_id=regiment_id, city_id=city_id)
        regiment_location = self.get_regiment_location(regiment_id)
        city_location = self.get_city_location(city_id)
        attack_result['attack_distance'] = self.get_tile_distance(regiment_location, city_location)
        return attack_result

    def reset_regiment_movement_for_new_turn(self):
        for regiment in self.regiments.values():
            regiment.reset_turn_movement()

    def reset_battle_resolution_for_new_turn(self):
        self.resolved_regiment_battles_this_turn.clear()
        self.resolved_sieges_this_turn.clear()

    def _apply_regiment_battle_losses(self, regiment: Regiment, casualty_count: int):
        casualties = {'infantry': 0, 'ranged': 0, 'cavalry': 0}
        total_combat_units = regiment.infantry + regiment.ranged + regiment.cavalry
        casualty_count = max(0, min(total_combat_units, casualty_count))
        if casualty_count == 0 or total_combat_units == 0:
            return casualties

        shares = []
        for unit_type in ('infantry', 'ranged', 'cavalry'):
            unit_count = getattr(regiment, unit_type)
            share = casualty_count * (unit_count / total_combat_units)
            assigned = math.floor(share)
            casualties[unit_type] = assigned
            shares.append((unit_type, share - assigned))

        casualties_remaining = casualty_count - sum(casualties.values())
        shares.sort(key=lambda item: item[1], reverse=True)
        for unit_type, _ in shares[:casualties_remaining]:
            casualties[unit_type] += 1

        regiment.update_composition(
            infantry=max(0, regiment.infantry - casualties['infantry']),
            ranged=max(0, regiment.ranged - casualties['ranged']),
            cavalry=max(0, regiment.cavalry - casualties['cavalry']),
            siege=regiment.siege,
        )
        return casualties

    def _remove_regiment_from_map(self, regiment_id: int):
        location = self.get_regiment_location(regiment_id)
        if location is not None:
            self.tiles[location].regiment_id = None
        self.regiments.pop(regiment_id, None)
        self.recalculate_tile_influence()

    def print_regiment_metadata(self, regiment: Regiment):
        if regiment is None:
            print('No regiment found.')
            return

        owner = self.get_player(regiment.owner_id)
        owner_name = owner.name if owner is not None else f'Unknown({regiment.owner_id})'
        owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
        if owner_color:
            owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
        location = self.get_regiment_location(regiment.id)
        location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'

        print('REGIMENT:')
        print(f'  id={regiment.id} | name={regiment.name} | owner={owner_name} | location={location_text}')
        print(f'  composition: infantry={regiment.infantry}, ranged={regiment.ranged}, cavalry={regiment.cavalry}, siege={regiment.siege}, heroes={regiment.hero_count()}')
        print(
            f'  scores: vs_regiment={regiment.regiment_attack_score}, vs_city={regiment.city_attack_score} '
            f'| move_range={regiment.movement_range()} | attack_range={regiment.attack_range()} '
            f'| line_of_sight={regiment.effective_line_of_sight_radius()}'
        )
        if regiment.heroes:
            print(f'  heroes: {", ".join(regiment.heroes)}')
        print('')

    def _normalize_player_color_name(self, player_color: str):
        return str(player_color).strip().lower().replace('_', '').replace('-', '')

    def _get_player_color_code(self, player_color: str):
        color_map = {
            'black': Fore.BLACK,
            'red': Fore.RED,
            'green': Fore.GREEN,
            'yellow': Fore.YELLOW,
            'blue': Fore.BLUE,
            'magenta': Fore.MAGENTA,
            'cyan': Fore.CYAN,
            'white': Fore.WHITE,
            'lightblack': Fore.LIGHTBLACK_EX,
            'lightred': Fore.LIGHTRED_EX,
            'lightgreen': Fore.LIGHTGREEN_EX,
            'lightyellow': Fore.LIGHTYELLOW_EX,
            'lightblue': Fore.LIGHTBLUE_EX,
            'lightmagenta': Fore.LIGHTMAGENTA_EX,
            'lightcyan': Fore.LIGHTCYAN_EX,
            'lightwhite': Fore.LIGHTWHITE_EX,
        }
        normalized = self._normalize_player_color_name(player_color)
        return color_map.get(normalized, '')

    def _get_player_color_rgb(self, player_color: str):
        color_map = {
            'black': (0, 0, 0),
            'red': (205, 49, 49),
            'green': (13, 188, 121),
            'yellow': (229, 229, 16),
            'blue': (36, 114, 200),
            'magenta': (188, 63, 188),
            'cyan': (17, 168, 205),
            'white': (229, 229, 229),
            'lightblack': (102, 102, 102),
            'lightred': (241, 76, 76),
            'lightgreen': (35, 209, 139),
            'lightyellow': (245, 245, 67),
            'lightblue': (59, 142, 234),
            'lightmagenta': (214, 112, 214),
            'lightcyan': (41, 184, 219),
            'lightwhite': (255, 255, 255),
        }
        normalized = self._normalize_player_color_name(player_color)
        return color_map.get(normalized)

    def _get_influence_gradient_color_code(self, player_color: str, influence_score: float):
        player_rgb = self._get_player_color_rgb(player_color)
        if player_rgb is None:
            return ''

        normalized_score = self._clamp_influence_score(influence_score)
        if normalized_score <= self.INFLUENCE_EPSILON:
            return ''

        blend_ratio = self.MIN_VISIBLE_INFLUENCE_COLOR_BLEND
        if normalized_score > self.MIN_VISIBLE_INFLUENCE_SCORE:
            scaled_score = (
                (normalized_score - self.MIN_VISIBLE_INFLUENCE_SCORE) /
                (self.MAX_INFLUENCE_SCORE - self.MIN_VISIBLE_INFLUENCE_SCORE)
            )
            blend_ratio += (1.0 - self.MIN_VISIBLE_INFLUENCE_COLOR_BLEND) * scaled_score
        blended_rgb = tuple(
            round(255 + ((channel - 255) * blend_ratio))
            for channel in player_rgb
        )
        return f'\033[38;2;{blended_rgb[0]};{blended_rgb[1]};{blended_rgb[2]}m'

    def _get_tile_symbol_for_view(self, tile: Tile, visible_tiles: set[tuple[int, int]] = None,
                                  discovered_tiles: set[tuple[int, int]] = None):
        if visible_tiles is not None and discovered_tiles is not None:
            position = (tile.x, tile.y)
            if position not in discovered_tiles:
                return ' ', None, None
            if position not in visible_tiles:
                return tile.symbol, None, None

        city = self.get_city(tile.city_id) if tile.city_id is not None else None
        regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
        if regiment is not None:
            return regiment.symbol(), city, regiment
        if city is not None:
            return city.symbol, city, regiment
        return tile.symbol, city, regiment

    def print(self, viewer_player_id: int = None):
        visible_tiles = None
        discovered_tiles = None
        if viewer_player_id is not None:
            visible_tiles = self.get_player_visible_tiles(viewer_player_id)
            discovered_tiles = self.update_player_discovery(viewer_player_id)

        # Get the max character length for each column of the map for proper alignment
        col_widths = []
        for x in range(self.width):
            col_width = len(str(x))
            for y in range(self.height):
                tile = self.tiles[(x, y)]
                symbol, _, _ = self._get_tile_symbol_for_view(tile, visible_tiles, discovered_tiles)
                col_width = max(col_width, len(symbol))
            col_widths.append(col_width)

        # Print the map
        print(f'\nMAP:')
        row_label_width = max(1, len(str(self.height - 1)))
        header_padding = ' ' * (row_label_width + 1)
        print(f"{header_padding}{' '.join(str(x).center(col_widths[x]) for x in range(self.width))}")
        for y in range(self.height):
            row_display = [str(y).rjust(row_label_width)]
            for x in range(self.width):
                tile = self.tiles[(x, y)]
                symbol, city, regiment = self._get_tile_symbol_for_view(tile, visible_tiles, discovered_tiles)
                display_symbol = symbol.center(col_widths[x])
                if viewer_player_id is not None and (x, y) not in visible_tiles:
                    row_display.append(display_symbol)
                    continue
                tile_owner = self.get_player(tile.influence_owner_id) if tile.influence_owner_id is not None else None
                influence_score = tile.influence_scores.get(tile_owner.id, 0.0) if tile_owner is not None else 0.0
                color_code = (
                    self._get_influence_gradient_color_code(tile_owner.color, influence_score)
                    if tile_owner is not None else ''
                )
                if color_code:
                    display_symbol = f'{color_code}{display_symbol}{Style.RESET_ALL}'
                row_display.append(display_symbol)
            print(' '.join(row_display))

        # Print the legend
        legend_entries = [f"{t}={Tile._allowable_types[t]['symbol']}" \
                          for t in Tile._allowable_types.keys()]
        for s in City._city_symbols:
            legend_entries.append(f'{s}={City._city_symbols[s]}')
        legend_entries.append('Regiment=R<id>(owner_id)')
        legend_entries.append('Undiscovered=<space>')
        legend_entries.append('Influence tint: 0.0=white, 0.01+=40% player color, 1.0=full player color')
        print('-----\nLEGEND:')
        for l in legend_entries:
            print(l, end='; ') if l != legend_entries[-1] else print(l)
        print('\n')

    def print_player_metadata(self, sort_by: str = 'influence', show_rank: bool = True):
        if not self.players:
            print('No player metadata is loaded.')
            return

        if sort_by == 'influence':
            player_entries = self.get_player_influence_rankings()
        elif sort_by in {'player_id', 'id'}:
            player_entries = [
                (player, self.get_player_total_influence_score(player.id))
                for player in sorted(self.players.values(), key=lambda player: player.id)
            ]
        else:
            raise ValueError(f'Unsupported player metadata sort order: {sort_by}')

        print('PLAYERS:')
        for rank, (player, total_influence_score) in enumerate(player_entries, start=1):
            color_code = self._get_player_color_code(player.color)
            prefix = f'{rank}. ' if show_rank else ''
            player_text = (
                f'{prefix}P{player.id}: {player.name} ({player.color}) | '
                f'total influence={total_influence_score:.2f}'
            )
            if color_code:
                player_text = f'{color_code}{player_text}{Style.RESET_ALL}'
            print(f'  {player_text}')
        print('')

    def print_city_metadata(self, viewer_player_id: int = None):
        if not self.cities:
            print('No city metadata is loaded.')
            return

        visible_tiles = None
        if viewer_player_id is not None:
            visible_tiles = self.get_player_visible_tiles(viewer_player_id)
            self.update_player_discovery(viewer_player_id)

        visible_city_count = 0
        print('CITIES:')
        for city in self.cities.values():
            location = self.get_city_location(city.id)
            if viewer_player_id is not None:
                if location is None or location not in visible_tiles:
                    continue
            visible_city_count += 1
            city_type = 'Capital' if city.is_capital else 'City'
            owner = self.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
            if owner_color:
                owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
            location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'
            print(
                f'  {city_type} {city.id}: {city.name} | owner={owner_name} | '
                f'population={city.population} | defense={city.defense_score} | '
                f'line_of_sight={city.effective_line_of_sight_radius()} | location={location_text}'
            )
        if visible_city_count == 0:
            print('  No cities or capitals are currently within line of sight.')
        print('')

class MapLoader:

    def __init__(self, filepath: str):
        with open(filepath, 'r', encoding='utf-8') as map_file:
            self.map_data = map_file.read()

    def parse(self):
        width = None
        height = None
        default_type = 'grass'
        explicit_tiles: dict[tuple[int, int], str] = {}
        players_data: dict[int, dict] = {}
        cities_data: dict[int, dict] = {}
        tile_city_attachments: dict[tuple[int, int], int] = {}
        tile_city_kinds: dict[tuple[int, int], str] = {}

        for line_number, raw_line in enumerate(self.map_data.splitlines(), start=1):
            line = raw_line.split('#', 1)[0].strip()
            if not line:
                continue
            parts = line.split()
            keyword = parts[0].lower()

            if keyword == 'size' and len(parts) == 3:
                width, height = int(parts[1]), int(parts[2])
            elif keyword == 'default' and len(parts) == 2:
                default_type = parts[1]
            elif keyword == 'player' and len(parts) >= 4:
                player_id = int(parts[1])
                player_color = parts[-1]
                player_name = ' '.join(parts[2:-1])
                players_data[player_id] = {
                    'id': player_id,
                    'name': player_name,
                    'color': player_color,
                }
            elif keyword in {'city', 'capital'} and len(parts) >= 5:
                city_id = int(parts[1])
                owner_id = int(parts[2])
                city_population = int(parts[-1])
                city_name = ' '.join(parts[3:-1])
                cities_data[city_id] = {
                    'id': city_id,
                    'name': city_name,
                    'owner_id': owner_id,
                    'population': city_population,
                    'is_capital': keyword == 'capital',
                }
            elif len(parts) == 4 and parts[2].lower() in {'city', 'capital'}:
                x, y = int(parts[0]), int(parts[1])
                city_id = int(parts[3])
                tile_city_attachments[(x, y)] = city_id
                tile_city_kinds[(x, y)] = parts[2].lower()
            elif len(parts) == 3:
                x, y, tile_type = int(parts[0]), int(parts[1]), parts[2]
                explicit_tiles[(x, y)] = tile_type
            else:
                raise ValueError(f'Unsupported map directive at line {line_number}: "{raw_line}"')

        if width is None or height is None:
            raise ValueError('Map file missing required "size" directive')

        game_map = Map(width=width, height=height, default_tile=default_type)

        for player_data in players_data.values():
            game_map.add_player(Player(
                id=player_data['id'],
                name=player_data['name'],
                color=player_data['color'],
            ))

        for city_data in cities_data.values():
            game_map.add_city(City(
                id=city_data['id'],
                name=city_data['name'],
                owner_id=city_data['owner_id'],
                population=city_data['population'],
                is_capital=city_data['is_capital'],
            ))

        for city_id in tile_city_attachments.values():
            if city_id not in game_map.cities:
                raise ValueError(f'Tile references undefined city_id={city_id}')

        for position, kind in tile_city_kinds.items():
            if kind == 'capital':
                game_map.cities[tile_city_attachments[position]].mark_as_capital()

        for y in range(height):
            for x in range(width):
                tile_type = explicit_tiles.get((x, y), default_type)
                game_map.tiles[(x, y)] = Tile(
                    type=tile_type,
                    x=x,
                    y=y,
                    city_id=tile_city_attachments.get((x, y)),
                )

        game_map.refresh_all_player_discovery()
        return game_map

class Menu:

    def __init__(self):
        self.options = []

    def add_option(self, title: str, listener = None, shortcut: str = None):
        if not isinstance(title, str) or not title.strip():
            raise ValueError('Menu option title must be a non-empty string')
        if listener is not None and not callable(listener):
            raise ValueError('Menu option listener must be callable')

        if shortcut is None:
            shortcut = title.strip()[0]
        if not isinstance(shortcut, str) or len(shortcut.strip()) != 1:
            raise ValueError('Menu option shortcut must be a single letter')

        self.options.append({
            'title': title.strip(),
            'shortcut': shortcut.strip().lower(),
            'listener': listener,
        })
        return len(self.options) - 1

    def set_listener(self, selection, listener):
        if not callable(listener):
            raise ValueError('Menu option listener must be callable')
        index = self._resolve_option_index(selection)
        self.options[index]['listener'] = listener

    def select_option(self, selection):
        index = self._resolve_option_index(selection)
        option = self.options[index]
        if option['listener'] is not None:
            return option['listener']()
        return option

    def _resolve_option_index(self, selection):
        if not self.options:
            raise ValueError('No menu options are available')

        if isinstance(selection, int):
            if 0 <= selection < len(self.options):
                return selection
            if 1 <= selection <= len(self.options):
                return selection - 1
            raise ValueError(f'Invalid menu selection: {selection}')

        normalized = str(selection).strip().lower()
        if not normalized:
            raise ValueError('Menu selection cannot be empty')

        if normalized.isdigit():
            selected = int(normalized)
            if 1 <= selected <= len(self.options):
                return selected - 1

        for index, option in enumerate(self.options):
            if normalized == option['title'].lower():
                return index
            if normalized == option['shortcut']:
                return index

        raise ValueError(f'Invalid menu selection: {selection}')

class ConsoleMenu(Menu):

    def __init__(self):
        super().__init__()

    def print_options(self):
        for index, option in enumerate(self.options, start=1):
            print(f'{index}. ({option["shortcut"]}) {option["title"]}')

    def prompt_and_select(self, prompt: str = 'Select an option: '):
        while True:
            self.print_options()
            selection = input(prompt)
            try:
                return self.select_option(selection)
            except ValueError as error:
                print(error)

class Game:

    def __init__(self, map = None):
        print('Game initialized.')
        self.map = map
        self.is_running = True
        self.player_in_loop = False
        self.selected_player_id = None
        self.turn = 0
        self.regiment_build_queue = []

    def get_selected_player(self):
        if self.map is None or self.selected_player_id is None:
            return None
        return self.map.get_player(self.selected_player_id)

    def select_player_empire(self):
        if self.map is None:
            raise ValueError('A map must be loaded before selecting an empire.')
        if not self.map.players:
            print('This map has no empires to select.')
            self.selected_player_id = None
            return False

        print('Choose an empire for this match:')
        self.map.print_player_metadata(sort_by='player_id', show_rank=False)

        while True:
            selection = input('Enter the empire/player id to control, or leave empty to cancel: ').strip()
            if not selection:
                print('Empire selection canceled.')
                self.selected_player_id = None
                return False
            if not selection.isdigit():
                print('Empire id must be a positive integer.')
                continue

            player_id = int(selection)
            selected_player = self.map.get_player(player_id)
            if selected_player is None:
                print(f'Empire {player_id} does not exist on this map.')
                continue

            self.selected_player_id = player_id
            print(f'You are now playing as {selected_player.name}.')
            return True

    def run(self):

        def start_new_game():
            print('Starting a new game...')
            while True:
                map_name = input('Enter the map file name (e.g., "test_map.map"), or leave empty to cancel: ').strip()
                if not map_name:
                    print('New game creation canceled.')
                    return
                map_path = Path(map_name)
                if not map_path.is_absolute():
                    map_path = Path(__file__).resolve().parent / map_path
                # print(f'#DEBUG: map_path = "{map_path}"')
                # print(f'#DEBUG: map_path.is_file() = {map_path.is_file()}')
                if not map_path.is_file():
                    print(f'Map file "{map_name}" does not exist in the game directory. Please provide a valid map file name.')
                    continue
                maploader = MapLoader(str(map_path))
                self.map = maploader.parse()
                self.turn = 0
                self.regiment_build_queue = []
                if not self.select_player_empire():
                    self.map = None
                    return
                self.player_in_loop = True
                player_loop()
                return

        def quit_to_main_menu():
            print('Are you sure you want to quit to the main menu? (y/n)')
            answer = input().strip().lower()
            if answer in ['y', 'yes']:
                self.player_in_loop = False
            else:
                print('Continuing the game.')

        def _determine_regiment_build_turns(city: City):
            return max(1, min(6, math.ceil(3000 / max(city.population, 1))))

        def _create_random_regiment_for_city(city: City, owner_id: int, regiment_name: str):
            total_units = max(8, city.population // 45 + random.randint(0, max(3, city.population // 200)))
            infantry = random.randint(total_units // 4, total_units // 2)
            remaining = total_units - infantry
            ranged = random.randint(0, remaining)
            remaining -= ranged
            cavalry = random.randint(0, remaining)
            siege = remaining - cavalry
            heroes = [f'Hero_{random.randint(1, 999)}'] if random.random() < 0.35 else []
            return Regiment(
                name=regiment_name,
                owner_id=owner_id,
                infantry=infantry,
                ranged=ranged,
                cavalry=cavalry,
                siege=siege,
                heroes=heroes,
            )

        def process_regiment_build_queue():
            if not self.regiment_build_queue:
                return

            completed_orders = []
            for order in self.regiment_build_queue:
                order['turns_remaining'] -= 1
                if order['turns_remaining'] > 0:
                    continue

                city = self.map.get_city(order['city_id'])
                city_location = self.map.get_city_location(order['city_id'])
                if city is None or city_location is None:
                    print(f"Build order canceled: City {order['city_id']} no longer has a valid location.")
                    completed_orders.append(order)
                    continue

                try:
                    regiment = _create_random_regiment_for_city(
                        city=city,
                        owner_id=order['owner_id'],
                        regiment_name=order['regiment_name'],
                    )
                    self.map.add_regiment(regiment, city_location[0], city_location[1])
                    print(f'Regiment formed: {regiment.symbol()} at city {city.name}.')
                    completed_orders.append(order)
                except ValueError as error:
                    # If the spawn tile is blocked, keep trying next turn.
                    print(f"Build order delayed for city {city.id}: {error}")
                    order['turns_remaining'] = 1

            self.regiment_build_queue = [o for o in self.regiment_build_queue if o not in completed_orders]

        def print_regiment_build_queue_status(show_empty_message: bool = True):
            selected_player = self.get_selected_player()
            visible_orders = self.regiment_build_queue
            if selected_player is not None:
                visible_orders = [order for order in self.regiment_build_queue if order['owner_id'] == selected_player.id]

            if not visible_orders:
                if show_empty_message:
                    print('No regiments are currently queued for production for your empire.')
                return

            print('REGIMENT BUILD QUEUE:')
            for order in visible_orders:
                city = self.map.get_city(order['city_id']) if self.map is not None else None
                city_name = city.name if city is not None else f'City {order["city_id"]}'
                turns_remaining = max(0, order['turns_remaining'])
                print(
                    f"  {turns_remaining} turn(s) until Regiment '{order['regiment_name']}' "
                    f'appears at {city_name}.'
                )
            print('')

        def create_regiment_order():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            city_id_raw = input('Enter city id to spawn regiment from: ').strip()
            if not city_id_raw.isdigit():
                print('City id must be a positive integer.')
                return

            city_id = int(city_id_raw)
            city = self.map.get_city(city_id)
            if city is None:
                print(f'City {city_id} does not exist.')
                return
            if city.owner_id != selected_player.id:
                print(f'City {city_id} belongs to another empire. You may only create regiments from {selected_player.name} cities.')
                return
            if any(
                order['city_id'] == city.id and order.get('queued_on_turn') == self.turn
                for order in self.regiment_build_queue
            ):
                print(f'{city.name} has already queued a regiment this turn.')
                return

            owner = self.map.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            default_name = f'{city.name} Guard'
            regiment_name = input(f'Enter regiment name (default: {default_name}): ').strip() or default_name

            turns_to_build = _determine_regiment_build_turns(city)
            self.regiment_build_queue.append({
                'city_id': city.id,
                'owner_id': city.owner_id,
                'regiment_name': regiment_name,
                'turns_remaining': turns_to_build,
                'queued_on_turn': self.turn,
            })
            print(f"Queued regiment '{regiment_name}' for {owner_name} from {city.name}. Ready in {turns_to_build} turn(s).")

        def _normalize_lookup_name(value: str):
            return str(value).strip().lower()

        def _find_regiments_by_name(name: str, owner_id: int = None):
            normalized_name = _normalize_lookup_name(name)
            if not normalized_name:
                return []
            return [
                regiment for regiment in self.map.regiments.values()
                if _normalize_lookup_name(regiment.name) == normalized_name
                and (owner_id is None or regiment.owner_id == owner_id)
            ]

        def _find_cities_by_name(name: str, owner_id: int = None):
            normalized_name = _normalize_lookup_name(name)
            if not normalized_name:
                return []
            return [
                city for city in self.map.cities.values()
                if _normalize_lookup_name(city.name) == normalized_name
                and (owner_id is None or city.owner_id == owner_id)
            ]

        def _resolve_owned_regiment(selection: str, owner_id: int):
            normalized = str(selection).strip()
            if not normalized:
                raise ValueError('Attacking regiment selection cannot be empty.')

            if normalized.isdigit():
                regiment_id = int(normalized)
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id != owner_id:
                    raise ValueError(f'Regiment {regiment_id} belongs to another empire.')
                return regiment

            matches = _find_regiments_by_name(normalized, owner_id=owner_id)
            if not matches:
                raise ValueError(f'No regiment named "{normalized}" belongs to your empire.')
            if len(matches) > 1:
                raise ValueError(f'Multiple regiments named "{normalized}" belong to your empire. Use the regiment id instead.')
            return matches[0]

        def _resolve_attack_target(selection: str, attacker_owner_id: int):
            normalized = str(selection).strip()
            if not normalized:
                raise ValueError('Target selection cannot be empty.')

            def _require_target_visibility(kind: str, entity_id: int, location: tuple[int, int] = None):
                if location is None:
                    raise ValueError(f'{kind} {entity_id} is not on the map.')
                if location not in self.map.get_player_visible_tiles(attacker_owner_id):
                    raise ValueError(f'{kind} {entity_id} is not currently visible to your empire.')

            compact = normalized.replace(' ', '')
            target_token = compact.upper()
            if target_token.startswith('*C') and compact[2:].isdigit():
                city_id = int(compact[2:])
                city = self.map.get_city(city_id)
                if city is None:
                    raise ValueError(f'City {city_id} does not exist.')
                if not city.is_capital:
                    raise ValueError(f'City {city_id} is not a capital.')
                if city.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('City', city_id, self.map.get_city_location(city_id))
                return {'kind': 'city', 'entity': city}

            if target_token.startswith('C') and compact[1:].isdigit():
                city_id = int(compact[1:])
                city = self.map.get_city(city_id)
                if city is None:
                    raise ValueError(f'City {city_id} does not exist.')
                if city.is_capital:
                    raise ValueError(f'City {city_id} is a capital. Target it as *C{city_id}.')
                if city.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('City', city_id, self.map.get_city_location(city_id))
                return {'kind': 'city', 'entity': city}

            if target_token.startswith('R') and compact[1:].isdigit():
                regiment_id = int(compact[1:])
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                _require_target_visibility('Regiment', regiment_id, self.map.get_regiment_location(regiment_id))
                return {'kind': 'regiment', 'entity': regiment}

            regiment_matches = [
                regiment for regiment in _find_regiments_by_name(normalized)
                if regiment.owner_id != attacker_owner_id
                and self.map.is_regiment_visible_to_player(regiment.id, attacker_owner_id)
            ]
            city_matches = [
                city for city in _find_cities_by_name(normalized)
                if city.owner_id != attacker_owner_id
                and self.map.is_city_visible_to_player(city.id, attacker_owner_id)
            ]
            target_matches = (
                [{'kind': 'regiment', 'entity': regiment} for regiment in regiment_matches] +
                [{'kind': 'city', 'entity': city} for city in city_matches]
            )
            if not target_matches:
                raise ValueError(f'No visible enemy regiment or city named "{normalized}" exists.')
            if len(target_matches) > 1:
                raise ValueError(f'Multiple enemy targets named "{normalized}" exist. Use R#, C#, or *C# instead.')
            return target_matches[0]

        def attack_with_regiment():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            attacker_input = input('Enter attacking regiment id or exact name: ').strip()
            try:
                attacker = _resolve_owned_regiment(attacker_input, selected_player.id)
            except ValueError as error:
                print(error)
                return

            target_input = input('Enter target (R#, C#, *C#, or exact name): ').strip()
            try:
                target = _resolve_attack_target(target_input, attacker.owner_id)
                if target['kind'] == 'regiment':
                    defending_regiment = target['entity']
                    result = self.map.attack_regiment(attacker.id, defending_regiment.id)
                    attacker_losses = sum(result['casualties_a'].values())
                    defender_losses = sum(result['casualties_b'].values())
                    print(
                        f'{attacker.symbol()} attacked {defending_regiment.symbol()} from '
                        f'{result["attack_distance"]} tile(s).'
                    )
                    print(
                        f'Attacker losses: {attacker_losses} | Defender losses: {defender_losses} | '
                        f'Remaining units: attacker={result["remaining_units_a"]}, defender={result["remaining_units_b"]}'
                    )
                    if result['defeated_a']:
                        print(f'{attacker.name} was destroyed.')
                    if result['defeated_b']:
                        print(f'{defending_regiment.name} was destroyed.')
                else:
                    target_city = target['entity']
                    city_type = 'Capital' if target_city.is_capital else 'City'
                    result = self.map.attack_city(attacker.id, target_city.id)
                    print(
                        f'{attacker.symbol()} attacked {city_type} {target_city.id} ({target_city.name}) from '
                        f'{result["attack_distance"]} tile(s).'
                    )
                    print(
                        f'Siege resistance: {result["resistance_before"]} -> '
                        f'{result["resistance_after"]} / {result["max_resistance"]}'
                    )
                    if result['sacked']:
                        new_owner = self.map.get_player(result['new_owner_id'])
                        new_owner_name = new_owner.name if new_owner is not None else f'Player {result["new_owner_id"]}'
                        print(f'{city_type} {target_city.name} was captured by {new_owner_name}.')
            except ValueError as error:
                print(error)

        def _parse_tile_coordinates(raw_value: str, label: str = 'Target tile'):
            parts = str(raw_value).strip().split()
            if len(parts) != 2:
                raise ValueError(f'{label} must be provided as two integers: x y')
            if not parts[0].lstrip('-').isdigit() or not parts[1].lstrip('-').isdigit():
                raise ValueError(f'{label} must be numeric coordinates.')
            return int(parts[0]), int(parts[1])

        def _build_split_counts(regiment: Regiment):
            split_counts = {}
            for unit_type in ('infantry', 'ranged', 'cavalry', 'siege'):
                percent_raw = input(
                    f'Enter percent of {unit_type} to move into the split regiment '
                    f'(0-100, current={getattr(regiment, unit_type)}): '
                ).strip()
                try:
                    percent = float(percent_raw)
                except ValueError as error:
                    raise ValueError(f'{unit_type.capitalize()} split percent must be a number.') from error
                if percent < 0 or percent > 100:
                    raise ValueError(f'{unit_type.capitalize()} split percent must be between 0 and 100.')
                split_counts[unit_type] = math.floor(getattr(regiment, unit_type) * (percent / 100))
            return split_counts

        def split_regiment_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            regiment_input = input('Enter regiment id or exact name to split: ').strip()
            try:
                regiment = _resolve_owned_regiment(regiment_input, selected_player.id)
                split_counts = _build_split_counts(regiment)
                print(
                    'New regiment composition: '
                    f"infantry={split_counts['infantry']}, ranged={split_counts['ranged']}, "
                    f"cavalry={split_counts['cavalry']}, siege={split_counts['siege']}"
                )
                target_x, target_y = _parse_tile_coordinates(
                    input('Enter adjacent tile for the split regiment as x y: '),
                    label='Split tile',
                )
                default_name = f'{regiment.name} Detachment'
                new_regiment_name = input(
                    f'Enter split regiment name (default: {default_name}): '
                ).strip() or default_name
                split_regiment = self.map.split_regiment(
                    regiment.id,
                    target_x,
                    target_y,
                    split_counts,
                    new_name=new_regiment_name,
                )
                print(
                    f"Split {regiment.symbol()} and formed {split_regiment.symbol()} at ({target_x}, {target_y}). "
                    f'Both regiments have spent their movement for this turn.'
                )
            except ValueError as error:
                print(error)

        def combine_regiments_action():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            source_input = input('Enter regiment id or exact name to combine from: ').strip()
            target_input = input('Enter regiment id or exact name to combine into: ').strip()
            try:
                source_regiment = _resolve_owned_regiment(source_input, selected_player.id)
                target_regiment = _resolve_owned_regiment(target_input, selected_player.id)
                combined_regiment = self.map.combine_regiments(source_regiment.id, target_regiment.id)
                print(
                    f'Combined {source_regiment.symbol()} into {combined_regiment.symbol()} at '
                    f'{self.map.get_regiment_location(combined_regiment.id)}. '
                    f'{combined_regiment.symbol()} kept its id and name and has spent its movement for this turn.'
                )
            except ValueError as error:
                print(error)

        def combine_or_split_regiment():
            action_menu = ConsoleMenu()
            action_menu.add_option('Split Regiment', split_regiment_action, 's')
            action_menu.add_option('Combine Regiments', combine_regiments_action, 'c')
            action_menu.add_option('Cancel', lambda: None, 'q')
            print('---COMBINE / SPLIT REGIMENT---')
            action_menu.prompt_and_select()

        def move_regiment():
            selected_player = self.get_selected_player()
            if selected_player is None:
                print('No empire is currently selected.')
                return

            regiment_id_raw = input('Enter regiment id to move: ').strip()
            if not regiment_id_raw.isdigit():
                print('Regiment id must be a positive integer.')
                return
            regiment_id = int(regiment_id_raw)
            regiment = self.map.get_regiment(regiment_id)
            if regiment is None:
                print(f'Regiment {regiment_id} does not exist.')
                return
            if regiment.owner_id != selected_player.id:
                print(f'Regiment {regiment_id} belongs to another empire. You may only move {selected_player.name} regiments.')
                return

            try:
                target_x, target_y = _parse_tile_coordinates(input('Enter target tile as x y: '))
                self.map.move_regiment(regiment_id, target_x, target_y)
                print(f'Moved {regiment.symbol()} to ({target_x}, {target_y}).')
            except ValueError as error:
                print(error)

        def print_visible_map():
            selected_player = self.get_selected_player()
            viewer_player_id = selected_player.id if selected_player is not None else None
            self.map.print(viewer_player_id=viewer_player_id)

        def print_visible_city_metadata():
            selected_player = self.get_selected_player()
            viewer_player_id = selected_player.id if selected_player is not None else None
            self.map.print_city_metadata(viewer_player_id=viewer_player_id)

        def print_regiment_metadata_by_id():
            selected_player = self.get_selected_player()
            regiment_id_raw = input('Enter regiment id to inspect: ').strip()
            if not regiment_id_raw.isdigit():
                print('Regiment id must be a positive integer.')
                return

            regiment_id = int(regiment_id_raw)
            regiment = self.map.get_regiment(regiment_id)
            if regiment is None:
                print(f'Regiment {regiment_id} does not exist.')
                return
            if (
                selected_player is not None and
                regiment.owner_id != selected_player.id and
                not self.map.is_regiment_visible_to_player(regiment.id, selected_player.id)
            ):
                print(f'Regiment {regiment_id} is not currently visible to your empire.')
                return
            self.map.print_regiment_metadata(regiment)

        def advance_turn():
            self.turn += 1
            self.map.reset_regiment_movement_for_new_turn()
            self.map.reset_battle_resolution_for_new_turn()
            process_regiment_build_queue()
            print_visible_map()
            self.map.print_player_metadata()
            print_regiment_build_queue_status(show_empty_message=False)

        def player_loop():
            player_menu = ConsoleMenu()
            player_menu.add_option('Print Map', print_visible_map, 'm')
            player_menu.add_option('Print Players', self.map.print_player_metadata, 'p')
            player_menu.add_option('Print Cities/Capitals', print_visible_city_metadata, 'c')
            player_menu.add_option('Create Regiment', create_regiment_order, 'r')
            player_menu.add_option('View Regiment Build Queue', print_regiment_build_queue_status, 'b')
            player_menu.add_option('Move Regiment', move_regiment, 'v')
            player_menu.add_option('Combine/Split Regiment', combine_or_split_regiment, 's')
            player_menu.add_option('Attack With Regiment', attack_with_regiment, 'a')
            player_menu.add_option('Inspect Regiment By Id', print_regiment_metadata_by_id, 'i')
            player_menu.add_option('Next Turn', advance_turn, 't')
            player_menu.add_option('Quit to Main Menu', quit_to_main_menu, 'q')
            advance_turn()  # Print the map at the start of the player loop
            while self.player_in_loop:
                selected_player = self.get_selected_player()
                print(f'Turn {self.turn}')
                if selected_player is not None:
                    print(f'Empire: {selected_player.name} (Player {selected_player.id})')
                print('---PLAYER OPTIONS---')
                player_menu.prompt_and_select()
                print('\n')

        main_menu = ConsoleMenu()
        main_menu.add_option('New Game', start_new_game, 'n')
        main_menu.add_option('Quit', lambda: setattr(self, 'is_running', False), 'q')

        while self.is_running:
            print('---MAIN MENU---')
            main_menu.prompt_and_select()
        # while(self.is_running):
        #     print(f'Turn {self.turn}:')
        #     print('The game is running. Continue? (y/n)')
        #     answer = input().strip().lower()
        #     if answer in ['y', 'yes']:
        #         self.turn += 1
        #         continue
        #     elif answer in ['n', 'no']:
        #         print('Exiting the game.')
        #         self.is_running = False
        #     else:
        #         print(f'"{answer}" is not a valid input.')

if __name__ == "__main__":
    # Clear the console to start
    os.system('cls' if os.name == 'nt' else 'clear')

    # Initialize and run the game
    game = Game()
    game.run()
