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
    RESISTANCE_MULTIPLIER = 5.0
    DEFENSE_SCALE = 1.0
    BASE_SIEGE_RATE = 0.20
    SIEGE_REGEN_RATE = 0.15
    SACK_POPULATION_PENALTY = 0.30
    
    def __init__(self, id: int, name: str, owner_id: int, 
                 population: int = 1000, is_capital: bool = False,
                 defense_score: float = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.population = population
        self.is_capital = is_capital
        self.defense_score = defense_score if defense_score is not None else self._default_defense_score()
        self.max_siege_resistance = self._default_max_siege_resistance()
        self.siege_resistance = self.max_siege_resistance
        self._update_symbol()

    def mark_as_capital(self):
        self.is_capital = True
        self.defense_score = self._default_defense_score()
        self.max_siege_resistance = self._default_max_siege_resistance()
        self.siege_resistance = self.max_siege_resistance
        self._update_symbol()

    def _default_defense_score(self):
        # Population and capital status provide a simple defensive baseline.
        return round(20 + (self.population / 200) + (10 if self.is_capital else 0), 2)

    def _default_max_siege_resistance(self):
        return round(self.defense_score * self.RESISTANCE_MULTIPLIER, 2)

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

    CITY_ATTACK_WEIGHTS = {
        'infantry': 0.8,
        'ranged': 0.7,
        'cavalry': 0.6,
        'siege': 1.6,
    }

    def __init__(self, id: int = None, name: str = 'Unnamed Regiment', owner_id: int = None,
                 infantry: int = 0, ranged: int = 0, cavalry: int = 0,
                 siege: int = 0, heroes: list[str] = None):
        self.id = id
        self.name = name
        self.owner_id = owner_id
        self.infantry = self._validate_unit_count(infantry, 'infantry')
        self.ranged = self._validate_unit_count(ranged, 'ranged')
        self.cavalry = self._validate_unit_count(cavalry, 'cavalry')
        self.siege = self._validate_unit_count(siege, 'siege')
        self.heroes = list(heroes) if heroes is not None else []

        self.regiment_attack_score = 0.0
        self.city_attack_score = 0.0
        self.movement_spent_this_turn = 0
        self.reorganized_this_turn = False
        self.recalculate_attack_scores()

    def _validate_unit_count(self, value: int, unit_type: str):
        if not isinstance(value, int) or value < 0:
            raise ValueError(f'{unit_type} count must be a non-negative integer')
        return value

    def total_units(self):
        return self.infantry + self.ranged + self.cavalry + self.siege

    def hero_count(self):
        return len(self.heroes)

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

    def __init__(self, width: int = 10, height: int = 10,
                 default_tile: str = 'grass'):
        self.width = width
        self.height = height
        self.default_tile = default_tile
        self.tiles = {}
        self.players: dict[int, Player] = {}
        self.cities: dict[int, City] = {}
        self.regiments: dict[int, Regiment] = {}
        self.next_regiment_id = 1
        self.resolved_regiment_battles_this_turn: set[tuple[int, int]] = set()
        self.resolved_sieges_this_turn: set[int] = set()

    def add_player(self, player: Player):
        self.players[player.id] = player

    def add_city(self, city: City):
        if city.owner_id not in self.players:
            raise ValueError(f'City {city.id} references missing player {city.owner_id}')
        self.cities[city.id] = city

    def get_player(self, player_id: int):
        return self.players.get(player_id)

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
            f'| move_range={regiment.movement_range()} | attack_range={regiment.attack_range()}'
        )
        if regiment.heroes:
            print(f'  heroes: {", ".join(regiment.heroes)}')
        print('')

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
        normalized = str(player_color).strip().lower().replace('_', '').replace('-', '')
        return color_map.get(normalized, '')

    def print(self):
        # Get the max character length for each column of the map for proper alignment
        col_widths = []
        for x in range(self.width):
            col_width = len(str(x))
            for y in range(self.height):
                tile = self.tiles[(x, y)]
                city = self.get_city(tile.city_id) if tile.city_id is not None else None
                regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
                if regiment is not None:
                    symbol = regiment.symbol()
                elif city is not None:
                    symbol = city.symbol
                else:
                    symbol = tile.symbol
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
                city = self.get_city(tile.city_id) if tile.city_id is not None else None
                regiment = self.get_regiment(tile.regiment_id) if tile.regiment_id is not None else None
                if regiment is not None:
                    symbol = regiment.symbol()
                elif city is not None:
                    symbol = city.symbol
                else:
                    symbol = tile.symbol
                display_symbol = symbol.center(col_widths[x])
                if regiment is not None:
                    owner = self.get_player(regiment.owner_id)
                    color_code = self._get_player_color_code(owner.color) if owner is not None else ''
                    if color_code:
                        display_symbol = f'{color_code}{display_symbol}{Style.RESET_ALL}'
                elif city is not None:
                    owner = self.get_player(city.owner_id)
                    color_code = self._get_player_color_code(owner.color) if owner is not None else ''
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
        print('-----\nLEGEND:')
        for l in legend_entries:
            print(l, end='; ') if l != legend_entries[-1] else print(l)
        print('\n')

    def print_player_metadata(self):
        if not self.players:
            print('No player metadata is loaded.')
            return

        print('PLAYERS:')
        for player in self.players.values():
            color_code = self._get_player_color_code(player.color)
            player_text = f'P{player.id}: {player.name} ({player.color})'
            if color_code:
                player_text = f'{color_code}{player_text}{Style.RESET_ALL}'
            print(f'  {player_text}')
        print('')

    def print_city_metadata(self):
        if not self.cities:
            print('No city metadata is loaded.')
            return

        print('CITIES:')
        for city in self.cities.values():
            city_type = 'Capital' if city.is_capital else 'City'
            owner = self.get_player(city.owner_id)
            owner_name = owner.name if owner is not None else f'Unknown({city.owner_id})'
            owner_color = self._get_player_color_code(owner.color) if owner is not None else ''
            if owner_color:
                owner_name = f'{owner_color}{owner_name}{Style.RESET_ALL}'
            location = self.get_city_location(city.id)
            location_text = f'({location[0]}, {location[1]})' if location is not None else 'UNPLACED'
            print(f'  {city_type} {city.id}: {city.name} | owner={owner_name} | population={city.population} | defense={city.defense_score} | location={location_text}')
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
        self.map.print_player_metadata()

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
                return {'kind': 'city', 'entity': city}

            if target_token.startswith('R') and compact[1:].isdigit():
                regiment_id = int(compact[1:])
                regiment = self.map.get_regiment(regiment_id)
                if regiment is None:
                    raise ValueError(f'Regiment {regiment_id} does not exist.')
                if regiment.owner_id == attacker_owner_id:
                    raise ValueError('Friendly fire is not allowed.')
                return {'kind': 'regiment', 'entity': regiment}

            regiment_matches = [
                regiment for regiment in _find_regiments_by_name(normalized)
                if regiment.owner_id != attacker_owner_id
            ]
            city_matches = [
                city for city in _find_cities_by_name(normalized)
                if city.owner_id != attacker_owner_id
            ]
            target_matches = (
                [{'kind': 'regiment', 'entity': regiment} for regiment in regiment_matches] +
                [{'kind': 'city', 'entity': city} for city in city_matches]
            )
            if not target_matches:
                raise ValueError(f'No enemy regiment or city named "{normalized}" exists.')
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

        def print_regiment_metadata_by_id():
            regiment_id_raw = input('Enter regiment id to inspect: ').strip()
            if not regiment_id_raw.isdigit():
                print('Regiment id must be a positive integer.')
                return

            regiment_id = int(regiment_id_raw)
            regiment = self.map.get_regiment(regiment_id)
            if regiment is None:
                print(f'Regiment {regiment_id} does not exist.')
                return
            self.map.print_regiment_metadata(regiment)

        def advance_turn():
            self.turn += 1
            self.map.reset_regiment_movement_for_new_turn()
            self.map.reset_battle_resolution_for_new_turn()
            process_regiment_build_queue()
            self.map.print()
            print_regiment_build_queue_status(show_empty_message=False)

        def player_loop():
            player_menu = ConsoleMenu()
            player_menu.add_option('Print Map', self.map.print, 'm')
            player_menu.add_option('Print Players', self.map.print_player_metadata, 'p')
            player_menu.add_option('Print Cities/Capitals', self.map.print_city_metadata, 'c')
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
